"""Possíveis duplicatas por similaridade de título (pg_trgm).

Complementa a dedup determinística (DOI/ISBN/hash) cobrindo o mesmo artigo
**sem DOI** ou com **DOI divergente** entre bases. Um humano confirma cada par:
**mesclar** (vira `duplicado_de`, soma origens, marca DUPLICADO) ou **descartar**
(registra que não são duplicatas, para não reaparecer).
"""

from __future__ import annotations

from django.contrib.postgres.search import TrigramSimilarity
from django.db import transaction

from .models import ParDuplicataDescartado, RegistroTriagem

LIMIAR = 0.6


def _pares_descartados(protocolo) -> set[frozenset]:
    pares = ParDuplicataDescartado.objects.filter(
        registro_a__protocolo=protocolo
    ).values_list("registro_a_id", "registro_b_id")
    return {frozenset(p) for p in pares}


def pares_possiveis(protocolo, limiar: float = LIMIAR, max_pares: int = 200) -> list[dict]:
    """Lista pares (a, b, sim) de registros em aberto com títulos semelhantes."""
    em_aberto = protocolo.registros.filter(
        status__in=RegistroTriagem.EM_ABERTO, ja_no_acervo=False
    )
    base = list(em_aberto.only("id", "titulo", "doi", "ano", "identificador"))
    descartados = _pares_descartados(protocolo)

    pares: list[dict] = []
    vistos: set[frozenset] = set()
    for r in base:
        candidatos = (
            em_aberto.exclude(pk=r.pk)
            .exclude(identificador=r.identificador)  # já não casam pela chave
            .annotate(sim=TrigramSimilarity("titulo", r.titulo))
            .filter(sim__gte=limiar, pk__gt=r.pk)
            .order_by("-sim")[:5]
        )
        for c in candidatos:
            chave = frozenset({r.pk, c.pk})
            if chave in descartados or chave in vistos:
                continue
            vistos.add(chave)
            pares.append({"a": r, "b": c, "sim": round(c.sim, 2)})

    pares.sort(key=lambda p: -p["sim"])
    return pares[:max_pares]


@transaction.atomic
def mesclar(canonico: RegistroTriagem, duplicado: RegistroTriagem) -> None:
    """Marca `duplicado` como DUPLICADO de `canonico` e funde as origens."""
    if canonico.pk == duplicado.pk:
        return
    for busca in duplicado.origem_buscas.all():
        canonico.origem_buscas.add(busca)
    duplicado.status = RegistroTriagem.Status.DUPLICADO
    duplicado.duplicado_de = canonico
    duplicado.save(update_fields=["status", "duplicado_de"])


def descartar(reg_a: RegistroTriagem, reg_b: RegistroTriagem) -> None:
    """Registra que o par NÃO é duplicata (ordena a<b)."""
    a, b = sorted((reg_a.pk, reg_b.pk))
    ParDuplicataDescartado.objects.get_or_create(registro_a_id=a, registro_b_id=b)
