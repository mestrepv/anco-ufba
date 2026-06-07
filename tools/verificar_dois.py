#!/usr/bin/env python3
"""
Verifica e classifica os DOIs do arquivo base_referencial_analise_cognitiva.

Uso:
    python tools/verificar_dois.py                          # só classificação local
    python tools/verificar_dois.py --verificar-online       # + consulta CrossRef (lento)
    python tools/verificar_dois.py --saida relatorio.csv    # exporta CSV

Categorias de saída:
    valido          — formato 10.XXXX/... correto
    prefixo_doi     — tem "DOI:" na frente, corrigível automaticamente
    invalido        — valor presente mas não é DOI (ISSN, número, etc.)
    vazio           — campo ausente ou em branco
"""

import argparse
import csv
import json
import re
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

DOI_RE = re.compile(r"^10\.\d{4,}/.+$")
CROSSREF_API = "https://api.crossref.org/works/{doi}"
CROSSREF_HEADERS = {"User-Agent": "AnCo-DOI-Checker/1.0 (mailto:paulovicente.ifba@gmail.com)"}


@dataclass
class ResultadoDOI:
    linha: int
    doi_original: str
    categoria: str  # valido | prefixo_doi | invalido | vazio
    doi_normalizado: str = ""
    online_ok: bool | None = None  # None = não verificado
    online_titulo: str = ""
    observacao: str = ""


def classificar(doi_raw: str) -> tuple[str, str, str]:
    """Retorna (categoria, doi_normalizado, observacao)."""
    doi = (doi_raw or "").strip()

    if not doi or doi == "-":
        return "vazio", "", ""

    # Remove prefixo "DOI:" ou "doi:" (com ou sem espaço)
    if re.match(r"(?i)^doi\s*:\s*", doi):
        doi_limpo = re.sub(r"(?i)^doi\s*:\s*", "", doi).strip()
        if DOI_RE.match(doi_limpo):
            return "prefixo_doi", doi_limpo, "removível com strip"
        return "invalido", doi, "tem prefixo 'DOI:' mas resto inválido"

    # URL do doi.org (ex: https://doi.org/10.1234/...)
    m = re.match(r"(?i)^https?://(?:dx\.)?doi\.org/(.+)$", doi)
    if m:
        doi_limpo = m.group(1)
        if DOI_RE.match(doi_limpo):
            return "prefixo_doi", doi_limpo, "URL doi.org — extraível"
        return "invalido", doi, "URL doi.org mas sufixo inválido"

    if DOI_RE.match(doi):
        return "valido", doi, ""

    # Scopus EID com DOI embutido: "2-s2.0-XXXXXXX ; 10.XXXX/..."
    m = re.match(r"^2-s2\.0-\d+\s*;\s*(.+)$", doi)
    if m:
        doi_embutido = m.group(1).strip()
        if DOI_RE.match(doi_embutido):
            return "prefixo_doi", doi_embutido, "Scopus EID com DOI extraível"
        return "invalido", doi, "Scopus EID sem DOI válido embutido"

    # Só Scopus EID, sem DOI
    if re.match(r"^2-s2\.0-\d+$", doi):
        return "invalido", doi, "apenas Scopus EID (sem DOI)"

    # Heurísticas para inválidos comuns
    if re.match(r"^\d{4}-\d{3}[\dX]$", doi):
        return "invalido", doi, "parece ISSN"
    if re.match(r"^[\d.]+$", doi):
        return "invalido", doi, "número avulso"
    if re.match(r"^\d+\.\d+E[+\-]\d+$", doi, re.I):
        return "invalido", doi, "notação científica (ISBN truncado?)"

    return "invalido", doi, "formato desconhecido"


def verificar_crossref(doi: str) -> tuple[bool, str]:
    """Consulta CrossRef. Retorna (existe, titulo_ou_erro)."""
    url = CROSSREF_API.format(doi=urllib.parse.quote(doi, safe=""))
    req = urllib.request.Request(url, headers=CROSSREF_HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read())
            titulo = body.get("message", {}).get("title", [""])[0]
            return True, titulo
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return False, "não encontrado no CrossRef"
        return False, f"HTTP {e.code}"
    except Exception as e:
        return False, str(e)


def processar(caminho: Path, verificar_online: bool) -> list[ResultadoDOI]:
    with caminho.open(encoding="utf-8") as f:
        dados = json.load(f)

    resultados = []
    total = len(dados)
    for i, registro in enumerate(dados):
        linha = registro.get("_linha", i + 2)
        doi_raw = registro.get("Numero_DOI", "") or ""
        categoria, doi_norm, obs = classificar(doi_raw)

        r = ResultadoDOI(
            linha=linha,
            doi_original=doi_raw,
            categoria=categoria,
            doi_normalizado=doi_norm,
            observacao=obs,
        )

        if verificar_online and categoria in ("valido", "prefixo_doi"):
            doi_consulta = doi_norm or doi_raw
            ok, info = verificar_crossref(doi_consulta)
            r.online_ok = ok
            r.online_titulo = info
            if not ok:
                r.categoria = "valido_nao_encontrado"
            # Respeita limite de ~50 req/s do CrossRef
            time.sleep(0.05)

        resultados.append(r)
        if (i + 1) % 100 == 0:
            print(f"  {i + 1}/{total}...", file=sys.stderr)

    return resultados


def imprimir_resumo(resultados: list[ResultadoDOI]) -> None:
    from collections import Counter

    contagem = Counter(r.categoria for r in resultados)
    total = len(resultados)
    print("\n=== RESUMO ===")
    for cat, n in sorted(contagem.items(), key=lambda x: -x[1]):
        pct = n / total * 100
        print(f"  {cat:<30} {n:>5}  ({pct:.1f}%)")
    print(f"  {'TOTAL':<30} {total:>5}")

    invalidos = [r for r in resultados if r.categoria == "invalido"]
    if invalidos:
        print(f"\n--- Inválidos por padrão (top 20 de {len(invalidos)}) ---")
        for r in invalidos[:20]:
            print(f"  linha {r.linha:>5}: {repr(r.doi_original):<45} {r.observacao}")

    corrigiveis = [r for r in resultados if r.categoria == "prefixo_doi"]
    if corrigiveis:
        print(f"\n--- Corrigíveis automaticamente (prefixo 'DOI:') — {len(corrigiveis)} ---")
        for r in corrigiveis[:10]:
            print(f"  linha {r.linha:>5}: {repr(r.doi_original)} → {repr(r.doi_normalizado)}")
        if len(corrigiveis) > 10:
            print(f"  ... e mais {len(corrigiveis) - 10}")

    nao_encontrados = [r for r in resultados if r.categoria == "valido_nao_encontrado"]
    if nao_encontrados:
        print(f"\n--- Formato válido mas não encontrado no CrossRef — {len(nao_encontrados)} ---")
        for r in nao_encontrados[:20]:
            print(f"  linha {r.linha:>5}: {r.doi_normalizado or r.doi_original}")
            print(f"           motivo: {r.online_titulo}")


def exportar_csv(resultados: list[ResultadoDOI], destino: Path) -> None:
    campos = [
        "linha",
        "categoria",
        "doi_original",
        "doi_normalizado",
        "online_ok",
        "online_titulo",
        "observacao",
    ]
    with destino.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=campos)
        w.writeheader()
        for r in resultados:
            w.writerow(
                {
                    "linha": r.linha,
                    "categoria": r.categoria,
                    "doi_original": r.doi_original,
                    "doi_normalizado": r.doi_normalizado,
                    "online_ok": "" if r.online_ok is None else r.online_ok,
                    "online_titulo": r.online_titulo,
                    "observacao": r.observacao,
                }
            )
    print(f"\nCSV exportado: {destino}")


def main() -> None:
    import urllib.parse  # noqa: F401 — garantir import para verificar_crossref

    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "arquivo",
        nargs="?",
        default="docs/base_referencial_analise_cognitiva (1).json",
        help="Caminho para o JSON da base (padrão: %(default)s)",
    )
    parser.add_argument(
        "--verificar-online",
        action="store_true",
        help="Consulta CrossRef para cada DOI de formato válido (lento ~1 min/100 DOIs)",
    )
    parser.add_argument(
        "--saida",
        metavar="ARQUIVO.csv",
        help="Exporta resultado detalhado como CSV",
    )
    args = parser.parse_args()

    caminho = Path(args.arquivo)
    if not caminho.exists():
        print(f"Arquivo não encontrado: {caminho}", file=sys.stderr)
        sys.exit(1)

    print(f"Lendo {caminho}...")
    resultados = processar(caminho, args.verificar_online)
    imprimir_resumo(resultados)

    if args.saida:
        exportar_csv(resultados, Path(args.saida))


if __name__ == "__main__":
    import urllib.parse

    main()
