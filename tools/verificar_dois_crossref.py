"""Valida DOIs recuperados consultando a API do Crossref.

Para cada DOI candidato:
  - GET https://api.crossref.org/works/{doi}
  - Verifica status (200 = existe; 404 = não existe; 4xx/5xx = falha)
  - Compara título Crossref com título esperado (similaridade)

Resultado por DOI:
  status: "ok"        → 200 + título bate (similaridade >= 0.75)
  status: "duvidoso"  → 200 mas título diverge
  status: "inexistente" → 404
  status: "erro_http" → outra resposta HTTP
  status: "erro_rede" → falha de conexão / timeout

Crossref pede User-Agent com email para entrar no "polite pool"
(rate limit mais generoso). Usar paulovicente@ifba.edu.br aqui.

Uso:
  python tools/verificar_dois_crossref.py /app/dois_recuperados.json /app/dois_verificados.json
"""

from __future__ import annotations

import json
import re
import sys
import time
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

USER_AGENT = "anco-importer/0.1 (mailto:paulovicente@ifba.edu.br)"
SLEEP_ENTRE_REQ = 0.05  # 20 req/s — polite pool da Crossref
TIMEOUT = 10
SIM_TITULO_OK = 0.75


def norm(s: str | None) -> str:
    if not s:
        return ""
    s = "".join(c for c in unicodedata.normalize("NFKD", str(s)) if not unicodedata.combining(c))
    s = s.lower().strip()
    return re.sub(r"\s+", " ", s)


def consultar_crossref(doi: str) -> tuple[str, dict | None, str]:
    """Retorna (status_http, payload_works, erro_msg)."""
    url = f"https://api.crossref.org/works/{doi}"
    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    try:
        with urlopen(req, timeout=TIMEOUT) as r:
            data = json.loads(r.read().decode("utf-8"))
            return "200", data.get("message", {}), ""
    except HTTPError as e:
        return str(e.code), None, e.reason or ""
    except URLError as e:
        return "rede", None, str(e.reason)
    except Exception as e:  # noqa: BLE001
        return "erro", None, str(e)


def comparar_titulos(esperado: str, recebido: str) -> float:
    if not esperado or not recebido:
        return 0.0
    return SequenceMatcher(None, norm(esperado), norm(recebido)).ratio()


def main(entrada: str, saida: str, max_n: int | None = None) -> None:
    mapping = json.load(open(entrada))
    matches = mapping["resultados"]

    # Deduplica por DOI: se 2 entradas apontam para o mesmo DOI, valida uma vez.
    por_doi: dict[str, list[dict]] = {}
    for m in matches:
        por_doi.setdefault(m["doi_recuperado"], []).append(m)

    dois = list(por_doi.keys())
    if max_n:
        dois = dois[:max_n]
    print(f"DOIs únicos a verificar: {len(dois)}")

    verificados = {}
    for i, doi in enumerate(dois, 1):
        if i % 25 == 0:
            print(f"  [{i}/{len(dois)}]")
        status_http, msg_data, erro = consultar_crossref(doi)

        if status_http == "200":
            titulos_cr = (msg_data or {}).get("title") or []
            titulo_cr = titulos_cr[0] if titulos_cr else ""
            # Pega o título de uma das ocorrências (provavelmente todas iguais)
            titulo_esperado = por_doi[doi][0]["titulo_revisada"]
            sim = comparar_titulos(titulo_esperado, titulo_cr)
            ano_cr = None
            issued = (msg_data or {}).get("issued", {}).get("date-parts", [])
            if issued and issued[0]:
                ano_cr = issued[0][0]
            status = "ok" if sim >= SIM_TITULO_OK else "duvidoso"
            verificados[doi] = {
                "status": status,
                "similaridade_titulo": round(sim, 3),
                "titulo_crossref": titulo_cr,
                "ano_crossref": ano_cr,
                "ocorrencias": len(por_doi[doi]),
            }
        elif status_http == "404":
            verificados[doi] = {
                "status": "inexistente",
                "ocorrencias": len(por_doi[doi]),
            }
        else:
            verificados[doi] = {
                "status": "erro_http" if status_http.isdigit() else "erro_rede",
                "http_code": status_http,
                "erro": erro,
                "ocorrencias": len(por_doi[doi]),
            }

        time.sleep(SLEEP_ENTRE_REQ)

    # Estatísticas
    from collections import Counter
    estat = Counter(v["status"] for v in verificados.values())
    print("\n=== Resultado da verificação ===")
    for s, n in estat.most_common():
        print(f"  {s:15s} {n}")

    payload = {
        "_meta": {
            "fonte": Path(entrada).name,
            "verificados": len(verificados),
            "estatisticas": dict(estat),
        },
        "verificados": verificados,
    }
    with open(saida, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"\nSalvo em: {saida}")


if __name__ == "__main__":
    if len(sys.argv) not in (3, 4):
        print("Uso: verificar_dois_crossref.py <entrada.json> <saida.json> [max_n]", file=sys.stderr)
        sys.exit(2)
    max_n = int(sys.argv[3]) if len(sys.argv) == 4 else None
    main(sys.argv[1], sys.argv[2], max_n)
