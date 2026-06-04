"""Contagens do fluxo PRISMA-ScR, derivadas dos status de `RegistroTriagem`.

Compõe o diagrama de fluxo (identificação → triagem → inclusão) e o export.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from django.db.models import Count, Sum

from .models import Busca, RegistroTriagem


@dataclass
class ContagemPrisma:
    identificados_relatado: int  # Σ Busca.n_identificados (relatado pelas bases)
    importados: int  # registros únicos após dedup
    duplicados_entre_bases: int  # mesma referência mesclada de >1 base
    ja_no_acervo: int  # casavam com Artigo existente (não triados)
    elegiveis: int  # importados - ja_no_acervo
    aguardando: int  # identificados, ainda não sorteados
    em_triagem: int
    incluidos: int
    excluidos: int
    excluidos_por_motivo: list = field(default_factory=list)
    n_buscas: int = 0

    def como_dict(self) -> dict:
        d = self.__dict__.copy()
        return d


def computar(protocolo) -> ContagemPrisma:
    regs = RegistroTriagem.objects.filter(protocolo=protocolo)
    S = RegistroTriagem.Status

    identificados = (
        Busca.objects.filter(protocolo=protocolo).aggregate(t=Sum("n_identificados"))["t"]
        or 0
    )
    importados = regs.count()
    # Duplicados entre bases: Σ(origens-1) = total de vínculos M2M - nº de registros.
    total_vinculos = (
        regs.aggregate(t=Count("origem_buscas"))["t"] or 0
    )
    duplicados_entre_bases = max(total_vinculos - importados, 0)

    ja_no_acervo = regs.filter(ja_no_acervo=True).count()
    por_motivo = list(
        regs.filter(status=S.EXCLUIDO)
        .exclude(motivo_exclusao="")
        .values("motivo_exclusao")
        .annotate(n=Count("id"))
        .order_by("-n")
    )

    return ContagemPrisma(
        identificados_relatado=identificados,
        importados=importados,
        duplicados_entre_bases=duplicados_entre_bases,
        ja_no_acervo=ja_no_acervo,
        elegiveis=importados - ja_no_acervo,
        aguardando=regs.filter(status=S.IDENTIFICADO, ja_no_acervo=False).count(),
        em_triagem=regs.filter(status=S.EM_TRIAGEM).count(),
        incluidos=regs.filter(status=S.INCLUIDO).count(),
        excluidos=regs.filter(status=S.EXCLUIDO).count(),
        excluidos_por_motivo=por_motivo,
        n_buscas=Busca.objects.filter(protocolo=protocolo).count(),
    )
