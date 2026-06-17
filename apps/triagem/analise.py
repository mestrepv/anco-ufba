"""Fila PRISMA de artigos a analisar.

A análise da Matriz AnCo, no módulo **PRISMA-ScR**, parte dos artigos
*incluídos* pela triagem. Este módulo centraliza o escopo dessa fila para que
painel (`apps/core`) e página (`apps/triagem`) usem a MESMA regra:

- só artigos com `RegistroTriagem` INCLUIDO;
- só em projetos PRISMA **ativos** (não arquivados);
- exclui o que o usuário já analisou.

A fila é um **pool self-serve**: qualquer analista pega qualquer incluído de
projeto ativo (não é restrita a membros do projeto). A fila de análise do módulo
**ANCO** é servida por `apps/anco` (sorteio / `AtribuicaoANCO`) e NÃO passa por
aqui — por isso registros de projetos ANCO antigos/arquivados (migrados para
`apps/anco`) não vazam para esta fila.
"""

from __future__ import annotations

from django.db.models import QuerySet

from .models import RegistroTriagem


def artigos_a_analisar(user) -> QuerySet:
    """Pool PRISMA de artigos a analisar por `user` (ver docstring do módulo)."""
    from apps.acervo.models import Analise, Artigo

    ja_minhas = Analise.objects.filter(analista=user).values_list("artigo_id", flat=True)
    return (
        Artigo.objects.filter(
            registros_triagem__status=RegistroTriagem.Status.INCLUIDO,
            registros_triagem__protocolo__arquivado=False,
        )
        .exclude(pk__in=ja_minhas)
        .distinct()
    )
