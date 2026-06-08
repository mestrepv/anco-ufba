"""Estatística consolidada artigos × bases (modo Revisão ANCO).

Cruza o **corpus pós-dedup** (registros `INCLUIDO`) com as bases de origem. A
fonte de verdade é `RegistroTriagem.origem_buscas` (M2M `Busca`): é o único lugar
que guarda a **sobreposição entre bases** por registro único após a dedup (a
mesma referência vinda de N bases é um só registro ligado a N buscas). Os
contadores de `Busca.n_*` contam antes da visão consolidada e incluem duplicados;
`Artigo.base_consulta` guarda apenas uma base — por isso não servem ao
cruzamento.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from django.db.models import Count

from .models import RegistroTriagem


@dataclass
class LinhaBase:
    base: str
    total: int = 0  # registros do corpus que vieram desta base
    exclusivos: int = 0  # registros que vieram **só** desta base
    compartilhados: int = 0  # registros desta base também presentes em outra(s)


@dataclass
class EstatisticasBases:
    por_base: list[LinhaBase] = field(default_factory=list)
    total_unicos: int = 0  # artigos únicos no corpus (pós-dedup)
    total_aparicoes: int = 0  # soma das origens (com repetição entre bases)
    duplicados_removidos: int = 0  # Σ(origens) − únicos


def _nome_base(busca) -> str:
    """Rótulo legível da base de uma `Busca`."""
    return busca.base_nome or f"Importação #{busca.pk}"


def estatisticas_por_base(projeto) -> EstatisticasBases:
    """Cruzamento artigos × bases no corpus pós-dedup de um projeto."""
    regs = (
        projeto.registros.filter(status=RegistroTriagem.Status.INCLUIDO)
        .annotate(n_origens=Count("origem_buscas"))
        .prefetch_related("origem_buscas")
    )

    linhas: dict[int, LinhaBase] = {}
    total_unicos = 0
    total_aparicoes = 0
    for reg in regs:
        total_unicos += 1
        exclusivo = reg.n_origens <= 1
        for busca in reg.origem_buscas.all():
            total_aparicoes += 1
            linha = linhas.get(busca.pk)
            if linha is None:
                linha = linhas[busca.pk] = LinhaBase(base=_nome_base(busca))
            linha.total += 1
            if exclusivo:
                linha.exclusivos += 1
            else:
                linha.compartilhados += 1

    por_base = sorted(linhas.values(), key=lambda x: (-x.total, x.base.lower()))
    return EstatisticasBases(
        por_base=por_base,
        total_unicos=total_unicos,
        total_aparicoes=total_aparicoes,
        duplicados_removidos=max(0, total_aparicoes - total_unicos),
    )
