"""Ponto de integração da relevância via **ASReview** (PRISMA-ScR).

Scaffolding (terreno preparado; integração pendente). A relevância interna
(termo-matching) foi removida na separação ANCO × PRISMA; a priorização da fila
de triagem passará a vir do ASReview (active learning). Ver
`docs/planos/integracao-asreview.md`.

Quando integrar:
- Abordagem A (serviço ao lado): `aplicar_ranking` recebe o export do ASReview
  (RIS/CSV com a ordem/rótulos) e grava a prioridade nos `RegistroTriagem`.
- Abordagem B (programática): `prioridade_para` roda o AL sobre o corpus e
  devolve o ranking {registro_id: posição}.

Nenhuma das funções deve ser chamada em produção ainda (levantam
`NotImplementedError` com a nota da decisão pendente).
"""

from __future__ import annotations

_PENDENTE = (
    "Integração do ASReview ainda não implementada — escolher abordagem "
    "(A: serviço ao lado / B: programática) em docs/planos/integracao-asreview.md."
)


def prioridade_para(projeto) -> dict[int, int]:
    """Devolve o ranking de relevância {registro_id: posição} do corpus do projeto.

    Abordagem B (programática): roda o active learning do ASReview sobre os
    registros incluídos/identificados e ordena por probabilidade de relevância.
    """
    raise NotImplementedError(_PENDENTE)


def aplicar_ranking(projeto, ranking: dict[int, int]) -> int:
    """Grava a `prioridade_asreview` nos `RegistroTriagem` a partir do `ranking`.

    Abordagem A (serviço ao lado): `ranking` vem do export do ASReview. Retorna
    quantos registros foram atualizados. (Requer o campo `prioridade_asreview`,
    a ser adicionado no momento da integração.)
    """
    raise NotImplementedError(_PENDENTE)
