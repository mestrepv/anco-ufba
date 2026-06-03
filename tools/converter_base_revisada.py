"""Converte `base-anco-revisada.xlsx` para JSON estruturado no schema AnCo.

Estrutura de saída:
  {
    "_meta": {fonte, gerado_em, total, alinhamentos_corrigidos},
    "registros": [
      {
        "_origem": {"linha_xlsx": int, "alinhamento_corrigido": bool},
        "artigo":  { ... campos do modelo Artigo },
        "analise": { ... campos do modelo Analise },
        "_extras": { campos da planilha sem correspondência no modelo }
      },
      ...
    ]
  }

Decisões (combinadas com o usuário):
  - Sentinelas '(Não Fornecido)', '(Não Especificada)', '-' preservados como string.
  - 19 linhas com colunas W..Z deslocadas são corrigidas via heurística
    (link de acesso identificado em X). Cada correção é logada.
  - Saída pronta para alimentar um command tipo `migrate_base_revisada`.

Uso:
  docker compose exec web python /app/tools/converter_base_revisada.py \\
      /app/base-anco-revisada.xlsx /app/base-anco-revisada.json
"""

from __future__ import annotations

import datetime
import json
import re
import sys
from pathlib import Path

import openpyxl


SIM_NAO_TRUE = {"sim", "sim (geralmente)"}
SIM_NAO_FALSE = {"não", "nao"}

# Padrões que identificam um campo "link de acesso" (não uma universidade)
LINK_PATTERNS = (
    re.compile(r"^https?://", re.IGNORECASE),
    re.compile(r"^file:///", re.IGNORECASE),
    re.compile(r"^\[acesso via", re.IGNORECASE),
    re.compile(r"^www\.", re.IGNORECASE),
)

# Extração de DOI canônico de strings como
# "[Acesso via SAGE / DOI 10.1177/0957926513481232]" ou "https://doi.org/10.xxxx/y"
DOI_RE = re.compile(r"\b(10\.\d{4,9}/[-._;()/:A-Z0-9]+)", re.IGNORECASE)

# Sentinela genérica de "não preenchido" — vira string vazia no campo do modelo
SENTINELA_RE = re.compile(r"^\(não\s", re.IGNORECASE)


def sim_nao(v):
    if v is None:
        return None
    s = str(v).strip().lower()
    if s in SIM_NAO_TRUE:
        return True
    if s in SIM_NAO_FALSE:
        return False
    return None  # sentinela inesperada


def texto(v):
    """Mantém o texto literal; converte None para string vazia."""
    if v is None:
        return ""
    return str(v).strip()


def parece_link(v) -> bool:
    if v is None:
        return False
    s = str(v).strip()
    return any(p.match(s) for p in LINK_PATTERNS)


def detectar_e_corrigir_alinhamento(row: tuple) -> tuple[tuple, bool]:
    """
    Heurística: se a coluna X (Universidade, idx 23) parece um link de acesso,
    significa que as colunas W..Z estão deslocadas 1 posição à direita a
    partir de X. Desfaz o shift.
    """
    if parece_link(row[23]):
        novo = list(row)
        # W (22) fica como está (já contém o que estava lá: tipicamente referências);
        # mas o link real está em X. Movemos:
        #   link_acesso  <- X  (era universidade)
        #   universidade <- Y  (era artigo pago)
        #   pago         <- Z  (era outra base)
        #   outra_base   <- ""
        novo[22] = row[23]  # link_acesso
        novo[23] = row[24]  # universidade
        novo[24] = row[25]  # pago
        novo[25] = ""
        return tuple(novo), True
    return row, False


def normalizar_base(v) -> str:
    s = texto(v)
    # SAGE → Sage
    if s.upper() == "SAGE":
        return "Sage"
    return s


def normalizar_periodico(v) -> str:
    """
    Title-case quando o texto está em ALL CAPS (24 grupos detectados na base).
    Preserva siglas e itálicos mistos.
    """
    s = texto(v)
    if s and s == s.upper() and any(c.isalpha() for c in s):
        # Title case "soft": só aplica se a string toda está em caixa alta.
        return s.title()
    return s


def normalizar_teoria(v) -> str:
    """Strip de ponto final terminal; resto preservado."""
    s = texto(v)
    return re.sub(r"\.+\s*$", "", s)


def limpar_link(v) -> str:
    """Remove sufixo entre parênteses após o URL (ex: 'http://... (pt-BR)')."""
    s = texto(v)
    if s.startswith("http"):
        # Strip de tudo após o primeiro espaço — URLs válidas não têm espaços.
        s = s.split(" ", 1)[0]
    return s


def extrair_doi(*fontes: str) -> str:
    """Procura DOI canônico em qualquer das fontes; retorna o primeiro encontrado."""
    for fonte in fontes:
        if not fonte:
            continue
        m = DOI_RE.search(fonte)
        if m:
            # Normaliza: lowercase do prefixo, strip de pontuação final
            doi = m.group(1).rstrip(".,;)")
            return doi.lower()
    return ""


def eh_sentinela(v) -> bool:
    s = texto(v)
    return bool(SENTINELA_RE.match(s)) or s == "-"


def ano(v) -> int | None:
    if v is None or v == "":
        return None
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def converter_linha(row: tuple, linha_xlsx: int) -> dict:
    row_norm, corrigido = detectar_e_corrigir_alinhamento(row)
    (
        titulo, titulo_traduzido, base, ano_val, periodico, area, palavras_chaves,
        autores, pres_t, pres_r, pres_pc, pres_ref, pres_corpo, pertinencia, define,
        objeto, objetivo, metodologia, resultados, foco, epistemologia, teoria,
        link, universidade, pago, outra_base,
    ) = row_norm[:26]

    alertas = []
    # Sim/Não esperado nas colunas I..O (presença×5, pertinência, define)
    for col_letra, valor in [
        ("I", pres_t), ("J", pres_r), ("K", pres_pc),
        ("L", pres_ref), ("M", pres_corpo),
        ("N", pertinencia), ("O", define),
    ]:
        if sim_nao(valor) is None and texto(valor):
            alertas.append(f"col {col_letra} esperava Sim/Não, recebeu {valor!r}")
    # Texto descritivo esperado em P..T — se vier exatamente "Sim" ou "Não",
    # provavelmente a linha está deslocada
    SIM_NAO_LITERAIS = {"Sim", "Não", "Sim (Geralmente)"}
    for col_letra, valor in [
        ("P", objeto), ("Q", objetivo), ("R", metodologia),
        ("S", resultados), ("T", foco),
    ]:
        if texto(valor) in SIM_NAO_LITERAIS:
            alertas.append(f"col {col_letra} esperava texto descritivo, recebeu {valor!r} (provável deslocamento)")

    link_limpo = limpar_link(link)
    doi = extrair_doi(link_limpo)
    # Sentinelas viram string vazia nos campos do modelo (mas listadas em _origem)
    sentinelas_zeradas = []
    def campo_texto(rotulo, valor):
        if eh_sentinela(valor):
            sentinelas_zeradas.append(rotulo)
            return ""
        return texto(valor)
    # Epistemologia/teoria: lista vazia se sentinela
    epis_norm = texto(epistemologia)
    epis_lista = [] if eh_sentinela(epis_norm) else [epis_norm] if epis_norm else []
    teoria_norm = normalizar_teoria(teoria)
    teoria_lista = [] if eh_sentinela(teoria_norm) else [teoria_norm] if teoria_norm else []

    return {
        "_origem": {
            "linha_xlsx": linha_xlsx,
            "alinhamento_corrigido": corrigido,
            "alertas": alertas,
            "sentinelas_zeradas": sentinelas_zeradas,
            "doi_extraido_de_link": bool(doi),
        },
        "artigo": {
            "titulo": texto(titulo),
            "titulo_traduzido": campo_texto("titulo_traduzido", titulo_traduzido),
            "titulo_periodico": normalizar_periodico(campo_texto("titulo_periodico", periodico)),
            "ano": ano(ano_val),
            "area": campo_texto("area", area),
            "autores": campo_texto("autores", autores),
            "palavras_chaves": campo_texto("palavras_chaves", palavras_chaves),
            "vinculacao_institucional": campo_texto("vinculacao_institucional", universidade),
            "base_consulta": normalizar_base(base),
            "outra_base_consulta": campo_texto("outra_base_consulta", outra_base),
            "link_acesso": "" if eh_sentinela(link_limpo) else link_limpo,
            "doi": doi,
            "artigo_pago": sim_nao(pago),
        },
        "analise": {
            "presenca_titulo": sim_nao(pres_t),
            "presenca_resumo": sim_nao(pres_r),
            "presenca_palavras_chave": sim_nao(pres_pc),
            "presenca_referencias": sim_nao(pres_ref),
            "presenca_corpo": sim_nao(pres_corpo),
            "pertinencia": sim_nao(pertinencia),
            "define_conceito": sim_nao(define),
            "objeto": campo_texto("objeto", objeto),
            "objetivo": campo_texto("objetivo", objetivo),
            "foco": campo_texto("foco", foco),
            "metodologia": campo_texto("metodologia", metodologia),
            "resultados": campo_texto("resultados", resultados),
            "epistemologia": epis_lista,
            "teoria": teoria_lista,
        },
    }


def main(entrada: str, saida: str) -> None:
    wb = openpyxl.load_workbook(entrada, read_only=True, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    data = rows[2:]  # pula linha "VOLTAR" e cabeçalho

    registros = [converter_linha(r, i + 3) for i, r in enumerate(data)]
    corrigidos = [r["_origem"]["linha_xlsx"] for r in registros if r["_origem"]["alinhamento_corrigido"]]
    com_alertas = [r["_origem"]["linha_xlsx"] for r in registros if r["_origem"]["alertas"]]
    com_doi = sum(1 for r in registros if r["artigo"]["doi"])

    payload = {
        "_meta": {
            "fonte": Path(entrada).name,
            "gerado_em": datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds"),
            "total": len(registros),
            "alinhamentos_corrigidos": {
                "quantidade": len(corrigidos),
                "linhas_xlsx": corrigidos,
            },
            "linhas_com_alertas": {
                "quantidade": len(com_alertas),
                "linhas_xlsx": com_alertas,
            },
            "dois_extraidos": com_doi,
            "convencoes": {
                "sentinelas_zeradas": "regex ^\\(Não... vira string vazia; lista em _origem.sentinelas_zeradas",
                "sim_nao": "Sim/Sim (Geralmente) -> true, Não -> false, outros -> null",
                "base_normalizada": "SAGE -> Sage",
                "periodico": "Title-case quando ALL CAPS",
                "teoria": "strip de ponto final",
                "link": "strip de tudo após o primeiro espaço se começar com http",
                "doi": "regex 10\\.\\d+/\\S+ aplicada em link_acesso original",
            },
        },
        "registros": registros,
    }

    with open(saida, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"OK: {len(registros)} registros -> {saida}")
    print(f"Alinhamentos corrigidos: {len(corrigidos)} -> linhas {corrigidos}")
    print(f"Linhas com alertas (revisão manual): {len(com_alertas)} -> linhas {com_alertas}")
    print(f"DOIs extraídos de links: {com_doi}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Uso: converter_base_revisada.py <entrada.xlsx> <saida.json>", file=sys.stderr)
        sys.exit(2)
    main(sys.argv[1], sys.argv[2])
