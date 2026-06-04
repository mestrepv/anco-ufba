"""Importação de candidatos para a triagem (RIS / BibTeX / CSV) + deduplicação.

Cada `Busca` (uma base) recebe um arquivo exportado. Os registros são
normalizados, deduplicados **dentro do protocolo** (mesma referência vinda de
várias bases é mesclada via `origem_buscas`) e **contra o acervo** (`Artigo`
existente, inclusive legado → marcado `ja_no_acervo`, não re-triado).

Idempotente: reimportar o mesmo arquivo na mesma `Busca` não duplica.
"""

from __future__ import annotations

import csv
import io
import logging
import re
from dataclasses import dataclass

from django.utils import timezone

from apps.acervo.models import _gerar_identificador_interno
from apps.acervo.services.crossref import normalizar_doi

from .models import Busca, RegistroTriagem, chave_dedup

logger = logging.getLogger(__name__)

FORMATOS = {"ris", "bibtex", "csv"}


# --------------------------------------------------------------------------- #
# Normalização de campos brutos
# --------------------------------------------------------------------------- #

def _txt(valor) -> str:
    """Achata str|list|None em texto; listas viram 'a; b; c'."""
    if valor is None:
        return ""
    if isinstance(valor, (list, tuple)):
        return "; ".join(str(v).strip() for v in valor if str(v).strip())
    return str(valor).strip()


def _primeiro(d: dict, *chaves) -> str:
    """Primeiro valor não-vazio dentre as chaves candidatas."""
    for c in chaves:
        v = _txt(d.get(c))
        if v:
            return v
    return ""


def _parse_ano(raw) -> int | None:
    m = re.search(r"(1[5-9]\d{2}|20\d{2}|21\d{2})", _txt(raw))
    return int(m.group(1)) if m else None


def _limpa_chaves(valor: str) -> str:
    """Remove chavetas do BibTeX e normaliza espaços."""
    return re.sub(r"\s+", " ", (valor or "").replace("{", "").replace("}", "")).strip()


# Códigos de tipo (RIS TY / BibTeX entrytype) → rótulo legível em pt-BR.
_TIPO_MAP = {
    "jour": "Artigo", "article": "Artigo",
    "book": "Livro",
    "chap": "Capítulo", "inbook": "Capítulo", "incollection": "Capítulo",
    "cpaper": "Trabalho de evento", "conf": "Trabalho de evento",
    "inproceedings": "Trabalho de evento", "conference": "Trabalho de evento",
    "thes": "Tese/Dissertação", "phdthesis": "Tese/Dissertação",
    "mastersthesis": "Tese/Dissertação",
    "rprt": "Relatório", "techreport": "Relatório",
    "review": "Resenha",
}


def _tipo_legivel(codigo) -> str:
    c = _txt(codigo).lower()
    return _TIPO_MAP.get(c, _txt(codigo).title())


# --------------------------------------------------------------------------- #
# Parsers por formato → lista de dicts normalizados
# --------------------------------------------------------------------------- #
# Saída padrão de cada parser: dicts com as chaves
#   titulo, autores, ano, doi, isbn, resumo, palavras_chaves,
#   titulo_periodico, idioma, link

def parse_ris(conteudo: str) -> list[dict]:
    import rispy

    registros: list[dict] = []
    for e in rispy.loads(conteudo):
        registros.append(
            {
                "titulo": _primeiro(e, "title", "primary_title", "translated_title"),
                "autores": _txt(e.get("authors") or e.get("first_authors")),
                "ano": _parse_ano(e.get("year") or e.get("publication_year") or e.get("date")),
                "doi": _primeiro(e, "doi"),
                "isbn": _primeiro(e, "isbn"),
                "resumo": _primeiro(e, "abstract", "notes_abstract"),
                "palavras_chaves": _txt(e.get("keywords")),
                "titulo_periodico": _primeiro(
                    e, "journal_name", "secondary_title", "alternate_title", "journal"
                ),
                "idioma": _primeiro(e, "language"),
                "link": _primeiro(e, "url", "urls"),
                "tipo": _tipo_legivel(e.get("type_of_reference")),
            }
        )
    return registros


def parse_bibtex(conteudo: str) -> list[dict]:
    import bibtexparser
    from bibtexparser.bparser import BibTexParser

    parser = BibTexParser(common_strings=True)
    parser.ignore_nonstandard_types = False
    db = bibtexparser.loads(conteudo, parser=parser)
    registros: list[dict] = []
    for e in db.entries:
        registros.append(
            {
                "titulo": _limpa_chaves(_primeiro(e, "title")),
                "autores": _limpa_chaves(_primeiro(e, "author")).replace(" and ", "; "),
                "ano": _parse_ano(e.get("year") or e.get("date")),
                "doi": _primeiro(e, "doi"),
                "isbn": _primeiro(e, "isbn"),
                "resumo": _limpa_chaves(_primeiro(e, "abstract")),
                "palavras_chaves": _limpa_chaves(_primeiro(e, "keywords", "keyword")),
                "titulo_periodico": _limpa_chaves(
                    _primeiro(e, "journal", "journaltitle", "booktitle")
                ),
                "idioma": _primeiro(e, "language", "langid"),
                "link": _primeiro(e, "url"),
                "tipo": _tipo_legivel(e.get("ENTRYTYPE")),
            }
        )
    return registros


# Mapa de cabeçalhos de CSV (canônico → variantes aceitas, minúsculas).
_CSV_MAPA = {
    "titulo": ("titulo", "título", "title", "ti"),
    "autores": ("autores", "autor", "authors", "author", "au"),
    "ano": ("ano", "year", "py", "data", "date"),
    "doi": ("doi", "do"),
    "isbn": ("isbn", "issn", "sn"),
    "resumo": ("resumo", "abstract", "ab"),
    "palavras_chaves": ("palavras_chaves", "palavras-chave", "keywords", "kw"),
    "titulo_periodico": ("titulo_periodico", "periodico", "periódico", "journal", "source", "fonte"),
    "idioma": ("idioma", "language", "la"),
    "link": ("link", "url", "ur", "link_acesso"),
    "tipo": ("tipo", "tipo_documento", "type", "document type", "dt", "ty"),
}


def parse_csv(conteudo: str) -> list[dict]:
    # Detecta delimitador (vírgula ou ponto-e-vírgula).
    amostra = conteudo[:2048]
    try:
        dialect = csv.Sniffer().sniff(amostra, delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    leitor = csv.DictReader(io.StringIO(conteudo), dialect=dialect)
    cabecalhos = {(h or "").strip().lower(): h for h in (leitor.fieldnames or [])}

    def col(linha: dict, canonico: str) -> str:
        for variante in _CSV_MAPA[canonico]:
            if variante in cabecalhos:
                return _txt(linha.get(cabecalhos[variante]))
        return ""

    registros: list[dict] = []
    for linha in leitor:
        registros.append(
            {
                "titulo": col(linha, "titulo"),
                "autores": col(linha, "autores"),
                "ano": _parse_ano(col(linha, "ano")),
                "doi": col(linha, "doi"),
                "isbn": col(linha, "isbn"),
                "resumo": col(linha, "resumo"),
                "palavras_chaves": col(linha, "palavras_chaves"),
                "titulo_periodico": col(linha, "titulo_periodico"),
                "idioma": col(linha, "idioma"),
                "link": col(linha, "link"),
                "tipo": _tipo_legivel(col(linha, "tipo")),
            }
        )
    return registros


def parse_conteudo(conteudo: str, formato: str) -> list[dict]:
    if formato == "ris":
        return parse_ris(conteudo)
    if formato == "bibtex":
        return parse_bibtex(conteudo)
    if formato == "csv":
        return parse_csv(conteudo)
    raise ValueError(f"Formato não suportado: {formato!r}")


def detectar_formato(nome_arquivo: str) -> str | None:
    nome = (nome_arquivo or "").lower()
    if nome.endswith(".ris") or nome.endswith(".nbib"):
        return "ris"
    if nome.endswith(".bib") or nome.endswith(".bibtex"):
        return "bibtex"
    if nome.endswith(".csv") or nome.endswith(".tsv"):
        return "csv"
    return None


def decodificar(bytes_arquivo: bytes) -> str:
    """UTF-8 com fallback latin-1 (exports de bases variam)."""
    for enc in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return bytes_arquivo.decode(enc)
        except UnicodeDecodeError:
            continue
    return bytes_arquivo.decode("utf-8", errors="replace")


# --------------------------------------------------------------------------- #
# Importação + deduplicação
# --------------------------------------------------------------------------- #

@dataclass
class ResultadoImportacao:
    total: int = 0
    criados: int = 0
    duplicados: int = 0  # mesma referência já no protocolo (mesclada)
    ja_no_acervo: int = 0  # casa com Artigo existente (inclusive legado)
    ignorados: int = 0  # sem título


def _artigo_no_acervo(doi: str, isbn: str, titulo: str, ano: int | None, periodico: str):
    """Retorna o `Artigo` existente correspondente, ou None. Inclui o legado."""
    from apps.acervo.models import Artigo

    if doi:
        a = Artigo.objects.filter(doi__iexact=doi).first()
        if a:
            return a
    if isbn:
        isbn_n = isbn.replace("-", "").replace(" ", "")
        a = Artigo.objects.filter(isbn__in=[isbn, isbn_n]).first()
        if a:
            return a
    ident = _gerar_identificador_interno(titulo, ano, periodico)
    return Artigo.objects.filter(identificador_interno=ident).first()


def importar_para_busca(busca: Busca, registros_brutos: list[dict]) -> ResultadoImportacao:
    """Cria/atualiza `RegistroTriagem` a partir de registros normalizados."""
    protocolo = busca.protocolo
    res = ResultadoImportacao()

    for bruto in registros_brutos:
        res.total += 1
        titulo = _txt(bruto.get("titulo"))
        if not titulo:
            res.ignorados += 1
            continue

        doi = normalizar_doi(bruto.get("doi") or "")
        isbn = _txt(bruto.get("isbn"))
        ano = bruto.get("ano")
        periodico = _txt(bruto.get("titulo_periodico"))
        ident = chave_dedup(doi, isbn, titulo, ano, periodico)

        existente = RegistroTriagem.objects.filter(
            protocolo=protocolo, identificador=ident
        ).first()
        if existente is not None:
            # Mesma referência já vista (possivelmente em outra base) → mescla origem.
            existente.origem_buscas.add(busca)
            res.duplicados += 1
            continue

        artigo = _artigo_no_acervo(doi, isbn, titulo, ano, periodico)
        reg = RegistroTriagem(
            protocolo=protocolo,
            titulo=titulo,
            autores=_txt(bruto.get("autores")),
            ano=ano,
            doi=doi,
            isbn=isbn,
            resumo=_txt(bruto.get("resumo")),
            palavras_chaves=_txt(bruto.get("palavras_chaves")),
            titulo_periodico=periodico,
            idioma=_txt(bruto.get("idioma"))[:20],
            link=_txt(bruto.get("link"))[:600],
            tipo=_txt(bruto.get("tipo"))[:40],
            identificador=ident,
        )
        if artigo is not None:
            reg.ja_no_acervo = True
            reg.artigo = artigo
            res.ja_no_acervo += 1
        else:
            res.criados += 1
        reg.save()
        reg.origem_buscas.add(busca)

    # Persiste o resultado da importação na própria busca (PRISMA por fonte).
    busca.n_lidos = res.total
    busca.n_novos = res.criados
    busca.n_duplicados = res.duplicados
    busca.n_ja_no_acervo = res.ja_no_acervo
    busca.n_ignorados = res.ignorados
    busca.importado_em = timezone.now()
    busca.save(
        update_fields=[
            "n_lidos", "n_novos", "n_duplicados", "n_ja_no_acervo",
            "n_ignorados", "importado_em",
        ]
    )

    logger.info(
        "Importação busca=%s base=%s total=%d criados=%d duplicados=%d ja_no_acervo=%d ignorados=%d",
        busca.pk, busca.base_nome, res.total, res.criados, res.duplicados,
        res.ja_no_acervo, res.ignorados,
    )
    return res
