"""Estatísticas do corpus ANCO — artigos × bases."""

from __future__ import annotations

from collections import Counter


def estatisticas_por_base(projeto) -> list[dict]:
    """Quantos itens do corpus (não removidos) vieram de cada base.

    Um item pode vir de mais de uma fonte/base (é contado em cada uma).
    """
    itens = projeto.itens.filter(removido=False).prefetch_related("origem_fontes__base_consulta")
    contagem: Counter[str] = Counter()
    for it in itens:
        for f in it.origem_fontes.all():
            contagem[f.base_nome or "(sem base)"] += 1
    return sorted(
        ({"base": base, "n": n} for base, n in contagem.items()),
        key=lambda x: (-x["n"], x["base"]),
    )


def resumo(projeto) -> dict:
    """Totais do corpus do projeto."""
    itens = projeto.itens.filter(removido=False)
    anos = [i.ano for i in itens if i.ano]
    return {
        "total": itens.count(),
        "ano_min": min(anos) if anos else None,
        "ano_max": max(anos) if anos else None,
        "por_base": estatisticas_por_base(projeto),
    }
