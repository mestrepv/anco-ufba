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
    "jour": "Artigo",
    "article": "Artigo",
    "book": "Livro",
    "chap": "Capítulo",
    "inbook": "Capítulo",
    "incollection": "Capítulo",
    "cpaper": "Trabalho de evento",
    "conf": "Trabalho de evento",
    "inproceedings": "Trabalho de evento",
    "conference": "Trabalho de evento",
    "thes": "Tese/Dissertação",
    "phdthesis": "Tese/Dissertação",
    "mastersthesis": "Tese/Dissertação",
    "rprt": "Relatório",
    "techreport": "Relatório",
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
    "titulo_periodico": (
        "titulo_periodico",
        "periodico",
        "periódico",
        "journal",
        "source",
        "fonte",
    ),
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


# Assinaturas de arquivos binários comuns que NÃO são exports de referências.
_BINARIOS = [
    (b"%PDF", "PDF"),
    (b"PK\x03\x04", "arquivo do Office (Word/Excel/ODF)"),
    (b"\xd0\xcf\x11\xe0", "arquivo antigo do Office (.doc/.xls)"),
    (b"{\\rtf", "documento RTF"),
]


def _tipo_binario(raw: bytes) -> str | None:
    for assinatura, nome in _BINARIOS:
        if raw[: len(assinatura)] == assinatura:
            return nome
    return None


def detectar_formato_conteudo(texto: str) -> str | None:
    """Detecta o formato pelo conteúdo, quando a extensão não resolve."""
    t = texto.lstrip()[:4000]
    if re.search(r"(^|\n)TY  - ", t) or re.search(r"(^|\n)ER  -", t):
        return "ris"
    if re.search(r"@\w+\s*\{", t):
        return "bibtex"
    primeira = t.splitlines()[0] if t.splitlines() else ""
    if ("," in primeira or ";" in primeira) and re.search(
        r"tit|doi|author|autor|ano|year", primeira, re.I
    ):
        return "csv"
    return None


def analisar_arquivo(nome: str, raw: bytes) -> dict:
    """Valida o arquivo enviado e conta os registros, com dica amigável.

    Retorna {ok, formato?, n?, erro?, dica?} — base do preview e do import.
    """
    if not raw:
        return {"ok": False, "erro": "O arquivo está vazio.", "dica": "Exporte de novo da base."}
    bin_ = _tipo_binario(raw)
    if bin_:
        return {
            "ok": False,
            "erro": f"Isso parece um {bin_}, não um export de referências.",
            "dica": "Exporte os resultados da base em RIS, BibTeX ou CSV — nunca PDF/Word/Excel.",
        }
    texto = decodificar(raw)
    formato = detectar_formato(nome) or detectar_formato_conteudo(texto)
    if not formato:
        return {
            "ok": False,
            "erro": "Não reconheci o formato do arquivo.",
            "dica": "Aceitamos RIS (.ris/.nbib), BibTeX (.bib) e CSV (.csv).",
        }
    try:
        registros = parse_conteudo(texto, formato)
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False, "formato": formato,
            "erro": f"Não consegui ler o arquivo ({exc}).",
            "dica": "Confira se o export saiu completo da base.",
        }
    n = len(registros)
    if n == 0:
        return {
            "ok": False, "formato": formato, "n": 0,
            "erro": "O arquivo foi lido, mas tem 0 registros.",
            "dica": "Verifique se você exportou os resultados (não uma página vazia).",
        }
    return {"ok": True, "formato": formato, "n": n}


# --------------------------------------------------------------------------- #
# Importação + deduplicação
# --------------------------------------------------------------------------- #

_STATUS_TRIADOS = RegistroTriagem.TRIADOS


def triagem_iniciada(busca) -> bool:
    """A triagem já começou para algum registro desta importação?"""
    return busca.registros.filter(status__in=_STATUS_TRIADOS).exists()


def busca_pode_excluir(busca) -> tuple[bool, str]:
    """Pré-triagem? (compat) — True se nada dela entrou em triagem ainda."""
    if triagem_iniciada(busca):
        return False, (
            "Esta importação já entrou em triagem — só o curador pode excluí-la "
            "(a triagem correspondente é apagada junto)."
        )
    return True, ""


def pode_excluir_busca(busca, user, projeto) -> tuple[bool, bool, str]:
    """Permissão de exclusão para `user`. Retorna (pode, cascata, motivo).

    - **Antes** da triagem: importador **ou** curador pode excluir (cascata=False).
    - **Depois** que a triagem começou: **só curador**, e a exclusão **apaga a
      triagem junto** (cascata=True).
    """
    eh_cur = projeto.eh_curador_no(user)
    if not triagem_iniciada(busca):
        if busca.criado_por_id == user.id or eh_cur:
            return True, False, ""
        return False, False, "Só quem importou (ou o curador) pode excluir esta importação."
    if eh_cur:
        return True, True, ""
    return False, False, ("A triagem já começou — só o curador pode excluir esta importação.")


def excluir_busca(busca, forcar: bool = False) -> tuple[bool, str]:
    """Exclui a importação e seus registros.

    Sem `forcar`, recusa se a triagem já começou (preserva o trabalho). Com
    `forcar` (curador), apaga também os registros já triados e suas decisões — a
    **triagem vai junto**. Registros compartilhados com outra busca são apenas
    desvinculados. `Artigo` promovido órfão (não-legado, sem análises e sem outro
    registro) é removido; o acervo curado nunca é tocado.
    """
    if not forcar and triagem_iniciada(busca):
        return False, busca_pode_excluir(busca)[1]
    for reg in list(busca.registros.all()):
        if reg.origem_buscas.count() <= 1:
            artigo = reg.artigo
            reg.delete()  # cascata: DecisaoTriagem
            if (
                artigo
                and not artigo.eh_legado
                and artigo.analises.count() == 0
                and not artigo.registros_triagem.exists()
            ):
                artigo.delete()
        else:
            reg.origem_buscas.remove(busca)
    if busca.arquivo:
        busca.arquivo.delete(save=False)
    busca.delete()
    return True, ""


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

        existente = RegistroTriagem.objects.filter(protocolo=protocolo, identificador=ident).first()
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
            "n_lidos",
            "n_novos",
            "n_duplicados",
            "n_ja_no_acervo",
            "n_ignorados",
            "importado_em",
        ]
    )

    logger.info(
        "Importação busca=%s base=%s total=%d criados=%d duplicados=%d ja_no_acervo=%d ignorados=%d",
        busca.pk,
        busca.base_nome,
        res.total,
        res.criados,
        res.duplicados,
        res.ja_no_acervo,
        res.ignorados,
    )
    return res
