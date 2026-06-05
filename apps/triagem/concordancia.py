"""Concordância entre revisores na triagem (para reporte metodológico).

Como os pares de revisores **variam por registro** (sorteio aleatório), a medida
adequada é o **κ de Fleiss** (n avaliadores fixo por item, avaliadores podendo
diferir entre itens), além do **percentual de acordo** simples.

Categorias: incluir / excluir / dúvida. Itens considerados = registros com TODAS
as decisões concluídas e em número igual a `protocolo.n_revisores`.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .models import DecisaoTriagem


@dataclass
class Concordancia:
    n_itens: int = 0
    n_revisores: int = 0
    perc_acordo: float | None = None  # 0..1
    kappa: float | None = None  # Fleiss
    interpretacao: str = "—"
    distribuicao: list = field(default_factory=list)  # [(categoria, n_atribuições)]

    @property
    def perc_pct(self) -> int | None:
        return round(self.perc_acordo * 100) if self.perc_acordo is not None else None

    def como_dict(self) -> dict:
        return {
            "concordancia_n_itens": self.n_itens,
            "concordancia_n_revisores": self.n_revisores,
            "concordancia_perc_acordo": (
                round(self.perc_acordo, 3) if self.perc_acordo is not None else None
            ),
            "concordancia_fleiss_kappa": (
                round(self.kappa, 3) if self.kappa is not None else None
            ),
            "concordancia_interpretacao": self.interpretacao,
        }


def _interpretar(kappa: float | None) -> str:
    """Escala de Landis & Koch (1977)."""
    if kappa is None:
        return "indefinida"
    if kappa < 0:
        return "pior que o acaso"
    if kappa <= 0.20:
        return "ligeira"
    if kappa <= 0.40:
        return "razoável"
    if kappa <= 0.60:
        return "moderada"
    if kappa <= 0.80:
        return "substancial"
    return "quase perfeita"


def calcular(protocolo) -> Concordancia:
    n = protocolo.n_revisores
    if n < 2:
        return Concordancia(n_revisores=n)

    # Decisões concluídas, agrupadas por registro.
    por_registro: dict[int, list[str]] = {}
    decisoes = DecisaoTriagem.objects.filter(
        registro__protocolo=protocolo,
        concluido_em__isnull=False,
        decisao__isnull=False,
    ).values_list("registro_id", "decisao")
    for rid, dec in decisoes:
        por_registro.setdefault(rid, []).append(dec)

    # Itens duplamente triados (exatamente n decisões → n constante p/ Fleiss).
    itens = [v for v in por_registro.values() if len(v) == n]
    N = len(itens)
    if N == 0:
        return Concordancia(n_itens=0, n_revisores=n)

    categorias = sorted({d for item in itens for d in item})
    idx = {c: i for i, c in enumerate(categorias)}
    k = len(categorias)

    # Percentual de acordo (todos os revisores na mesma categoria).
    acordos = sum(1 for item in itens if len(set(item)) == 1)
    perc = acordos / N

    # Fleiss' kappa.
    totais_cat = [0] * k
    soma_Pi = 0.0
    for item in itens:
        contagem = [0] * k
        for d in item:
            contagem[idx[d]] += 1
        for j in range(k):
            totais_cat[j] += contagem[j]
        soma_Pi += (sum(c * c for c in contagem) - n) / (n * (n - 1))
    P_bar = soma_Pi / N
    p_j = [totais_cat[j] / (N * n) for j in range(k)]
    P_e = sum(p * p for p in p_j)
    kappa = (P_bar - P_e) / (1 - P_e) if (1 - P_e) > 1e-9 else None

    rotulos = dict(
        DecisaoTriagem._meta.get_field("decisao").choices or []
    )
    distribuicao = [(rotulos.get(c, c), totais_cat[idx[c]]) for c in categorias]

    return Concordancia(
        n_itens=N,
        n_revisores=n,
        perc_acordo=perc,
        kappa=kappa,
        interpretacao=_interpretar(kappa),
        distribuicao=distribuicao,
    )
