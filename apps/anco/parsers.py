"""Parsers de listas bibliográficas (RIS/BibTeX/CSV) do módulo ANCO.

**Cópia própria** (independência total do `apps/triagem`, por decisão de projeto).
Saída padrão de cada parser: dicts com as chaves `titulo, autores, ano, doi, isbn,
resumo, palavras_chaves, titulo_periodico, idioma, link, tipo`.

> Nota: este encanamento é duplicado do `apps/triagem/importacao.py`. Correções de
> bug de parsing precisam ser aplicadas **nos dois lugares**.
"""

from __future__ import annotations

import csv
import io
import re

FORMATOS = {"ris", "bibtex", "csv", "medline"}


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


_URL_EMBUTIDA_RE = re.compile(r"^https?://[^\s]*?(https?://[^\s]+)$", re.I)


def normalizar_url(valor) -> str:
    """Desfaz URLs com esquema embutido (`https://doi.org/https://…`).

    Alguns exports do Zotero gravam o campo URL como `https://doi.org/` colado a
    uma URL já completa, gerando links quebrados como
    `https://doi.org/https://doi.org/10.x/y`. Recupera a URL interna real,
    aplicando de forma repetida (idempotente) até não restar esquema embutido.
    """
    url = _txt(valor)
    while (m := _URL_EMBUTIDA_RE.match(url)) is not None:
        url = m.group(1)
    return url


def _limpa_chaves(valor: str) -> str:
    """Remove chavetas do BibTeX e normaliza espaços."""
    return re.sub(r"\s+", " ", (valor or "").replace("{", "").replace("}", "")).strip()


_TIPO_MAP = {
    "jour": "Artigo",
    "article": "Artigo",
    "journalarticle": "Artigo",  # Zotero
    "journal article": "Artigo",  # MEDLINE PT
    "book": "Livro",
    "chap": "Capítulo",
    "inbook": "Capítulo",
    "incollection": "Capítulo",
    "booksection": "Capítulo",  # Zotero
    "cpaper": "Trabalho de evento",
    "conf": "Trabalho de evento",
    "conferencepaper": "Trabalho de evento",  # Zotero
    "inproceedings": "Trabalho de evento",
    "conference": "Trabalho de evento",
    "thes": "Tese/Dissertação",
    "thesis": "Tese/Dissertação",  # Zotero
    "phdthesis": "Tese/Dissertação",
    "doctoralthesis": "Tese/Dissertação",
    "mastersthesis": "Tese/Dissertação",
    "rprt": "Relatório",
    "report": "Relatório",  # Zotero
    "techreport": "Relatório",
    "review": "Resenha",
}


def _tipo_legivel(codigo) -> str:
    c = _txt(codigo).lower()
    return _TIPO_MAP.get(c, _txt(codigo).title())


# --------------------------------------------------------------------------- #
# Parsers por formato → lista de dicts normalizados
# --------------------------------------------------------------------------- #


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
                "link": normalizar_url(_primeiro(e, "url", "urls")),
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
                "link": normalizar_url(_primeiro(e, "url")),
                "tipo": _tipo_legivel(e.get("ENTRYTYPE")),
            }
        )
    return registros


_CSV_MAPA = {
    "titulo": ("titulo", "título", "title", "ti"),
    "autores": ("autores", "autor", "authors", "author", "au"),
    "ano": ("ano", "year", "py", "data", "date"),
    "doi": ("doi", "do"),
    "isbn": ("isbn", "issn", "sn"),
    # "abstract note" = Zotero; "resumen" = bases em espanhol.
    "resumo": ("resumo", "abstract", "abstract note", "resumen", "ab"),
    # "author keywords"/"index keywords"/"keywords plus" = WoS/Scopus;
    # "manual tags"/"automatic tags" = Zotero; "de"/"id" = códigos WoS.
    "palavras_chaves": (
        "palavras_chaves",
        "palavras-chave",
        "keywords",
        "author keywords",
        "index keywords",
        "keywords plus",
        "manual tags",
        "automatic tags",
        "de",
        "id",
        "kw",
    ),
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
    "tipo": ("tipo", "tipo_documento", "item type", "type", "document type", "dt", "ty"),
}


def parse_csv(conteudo: str) -> list[dict]:
    amostra = conteudo[:2048]
    try:
        dialect = csv.Sniffer().sniff(amostra, delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    leitor = csv.DictReader(io.StringIO(conteudo), dialect=dialect)
    cabecalhos = {(h or "").strip().lower(): h for h in (leitor.fieldnames or [])}

    def col(linha: dict, canonico: str) -> str:
        # Primeiro variante presente **e não-vazio** (ex.: "manual tags" vazia não
        # deve mascarar "automatic tags" preenchida).
        for variante in _CSV_MAPA[canonico]:
            if variante in cabecalhos:
                valor = _txt(linha.get(cabecalhos[variante]))
                if valor:
                    return valor
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
                "link": normalizar_url(col(linha, "link")),
                "tipo": _tipo_legivel(col(linha, "tipo")),
            }
        )
    return registros


_MEDLINE_TAG = re.compile(r"^([A-Z][A-Z0-9]{1,3})\s*- (.*)$")


def _medline_get(campos: dict[str, list[str]], *tags: str) -> list[str]:
    """Primeiro valor não-vazio dentre as tags MEDLINE candidatas."""
    for t in tags:
        if campos.get(t):
            return campos[t]
    return []


def parse_medline(conteudo: str) -> list[dict]:
    """Parser do formato MEDLINE (arquivos `.nbib` exportados do PubMed).

    MEDLINE parece RIS (tags `TI  - `, `AB  - `) mas não tem `TY  - `/`ER  - `;
    os registros são separados por linha em branco e há linhas de continuação
    (indentadas). Mapeia as tags do PubMed para o dict normalizado padrão.
    """
    registros: list[dict] = []
    # PubMed exporta com CRLF; sem normalizar, o separador de registros vira
    # `\r\n\r\n` e o split abaixo não casa (o `\r` não está em `[ \t]`),
    # colapsando todos os registros num só.
    conteudo = conteudo.replace("\r\n", "\n").replace("\r", "\n")
    for bloco in re.split(r"\n[ \t]*\n", conteudo.strip()):
        campos: dict[str, list[str]] = {}
        tag = None
        for linha in bloco.splitlines():
            m = _MEDLINE_TAG.match(linha)
            if m:
                tag = m.group(1)
                campos.setdefault(tag, []).append(m.group(2).strip())
            elif tag and linha[:1].isspace() and campos.get(tag):
                campos[tag][-1] += " " + linha.strip()
        if not campos:
            continue

        # DOI: das tags LID/AID marcadas com [doi]
        doi = ""
        for val in campos.get("LID", []) + campos.get("AID", []):
            mm = re.match(r"(10\.\S+?)\s*\[doi\]", val, re.I)
            if mm:
                doi = mm.group(1)
                break

        pmid = (campos.get("PMID") or [""])[0].strip()
        kws = campos.get("OT", []) + campos.get("MH", [])  # keywords do autor + MeSH
        registros.append(
            {
                "titulo": " ".join(_medline_get(campos, "TI")),
                "autores": "; ".join(_medline_get(campos, "FAU", "AU")),
                "ano": _parse_ano((_medline_get(campos, "DP", "DA") or [""])[0]),
                "doi": doi,
                "isbn": "",
                "resumo": " ".join(_medline_get(campos, "AB")),
                "palavras_chaves": "; ".join(k for k in kws if k),
                "titulo_periodico": (_medline_get(campos, "JT", "TA") or [""])[0],
                "idioma": (_medline_get(campos, "LA") or [""])[0],
                "link": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else "",
                "tipo": _tipo_legivel((_medline_get(campos, "PT") or ["Artigo"])[0]),
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
    if formato == "medline":
        return parse_medline(conteudo)
    raise ValueError(f"Formato não suportado: {formato!r}")


def detectar_formato(nome_arquivo: str) -> str | None:
    nome = (nome_arquivo or "").lower()
    if nome.endswith(".ris"):
        return "ris"
    if nome.endswith(".bib") or nome.endswith(".bibtex"):
        return "bibtex"
    if nome.endswith(".csv") or nome.endswith(".tsv"):
        return "csv"
    # `.nbib` fica para a detecção por conteúdo: o PubMed exporta MEDLINE nesse
    # nome, mas alguns gerenciadores salvam RIS com a mesma extensão.
    return None


def decodificar(bytes_arquivo: bytes) -> str:
    """UTF-8 com fallback latin-1 (exports de bases variam)."""
    for enc in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return bytes_arquivo.decode(enc)
        except UnicodeDecodeError:
            continue
    return bytes_arquivo.decode("utf-8", errors="replace")


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
    # MEDLINE (PubMed .nbib): tem PMID- e NÃO tem TY  - (que marca RIS).
    if re.search(r"(^|\n)PMID- ", t) and not re.search(r"(^|\n)TY  - ", t):
        return "medline"
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
    """Valida o arquivo enviado e conta os registros, com dica amigável."""
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
            "dica": "Aceitamos RIS (.ris), BibTeX (.bib), CSV (.csv) e PubMed (.nbib).",
        }
    try:
        registros = parse_conteudo(texto, formato)
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "formato": formato,
            "erro": f"Não consegui ler o arquivo ({exc}).",
            "dica": "Confira se o export saiu completo da base.",
        }
    n = len(registros)
    if n == 0:
        return {
            "ok": False,
            "formato": formato,
            "n": 0,
            "erro": "O arquivo foi lido, mas tem 0 registros.",
            "dica": "Verifique se você exportou os resultados (não uma página vazia).",
        }
    amostra = [
        (r.get("titulo") or "").strip() for r in registros[:4] if (r.get("titulo") or "").strip()
    ]
    return {"ok": True, "formato": formato, "n": n, "amostra": amostra}
