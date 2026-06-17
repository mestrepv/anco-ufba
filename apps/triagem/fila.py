"""Fila de triagem do revisor ("minhas triagens").

Centraliza o escopo das `DecisaoTriagem` que contam como trabalho pendente de um
revisor, para que painel (`apps/core`) e views da triagem usem a MESMA regra:

- só decisões do próprio usuário como revisor;
- só em projetos PRISMA **ativos** (não arquivados);
- só de projetos dos quais o usuário **ainda é membro**.

O sorteio é restrito aos membros do projeto (Fase 12); assignments órfãos — de
ex-membros ou de projetos arquivados — NÃO viram trabalho na fila do usuário.
"""

from __future__ import annotations

from django.db.models import QuerySet

from .models import DecisaoTriagem


def decisoes_do_revisor(user) -> QuerySet:
    """Todas as `DecisaoTriagem` de `user` em projetos ativos dos quais é membro."""
    return DecisaoTriagem.objects.filter(
        revisor=user,
        registro__protocolo__arquivado=False,
        registro__protocolo__membros__usuario=user,
    )


def decisoes_pendentes(user) -> QuerySet:
    """Subconjunto pendente (ainda não concluído) de `decisoes_do_revisor`."""
    return decisoes_do_revisor(user).filter(concluido_em__isnull=True)
