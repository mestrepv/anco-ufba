"""Fixtures/utilitários compartilhados dos testes da triagem (Fase 12)."""

import pytest
from django.urls import reverse

from apps.triagem.models import ProjetoMembro, ProtocoloTriagem

# Rotas escopadas por projeto (precisam do slug como 1º argumento).
PROJETO_ROTAS = {
    "triagem_painel",
    "triagem_importar",
    "triagem_registros",
    "triagem_duplicatas",
    "triagem_duplicatas_mescladas",
    "triagem_duplicata_mesclar",
    "triagem_duplicata_descartar",
    "triagem_duplicata_desfazer",
    "triagem_iniciar",
    "triagem_desempate",
    "triagem_desempatar",
    "triagem_prisma",
    "triagem_protocolo",
    "triagem_checklist",
    "triagem_calibracao",
    "triagem_busca_resumo",
    "triagem_busca_excluir",
    "triagem_importar_preview",
}


def turl(nome, *posargs, args=None):
    """Como `reverse`, mas injeta o slug do projeto ativo nas rotas escopadas."""
    extra = list(args) if args is not None else list(posargs)
    if nome in PROJETO_ROTAS:
        return reverse(nome, args=[ProtocoloTriagem.ativo().slug, *extra])
    return reverse(nome, args=extra)


@pytest.fixture
def proj(db):
    """Projeto ativo (com slug auto-gerado)."""
    return ProtocoloTriagem.ativo()


def inscrever(projeto, *usuarios, papel=ProjetoMembro.Papel.ANALISTA):
    """Inscreve usuários como membros do projeto (necessário p/ acesso e sorteio)."""
    for u in usuarios:
        ProjetoMembro.objects.get_or_create(projeto=projeto, usuario=u, defaults={"papel": papel})


def membro(usuario, papel=ProjetoMembro.Papel.ANALISTA):
    """Cria o vínculo do usuário ao projeto ativo e o devolve (encadeável)."""
    inscrever(ProtocoloTriagem.ativo(), usuario, papel=papel)
    return usuario
