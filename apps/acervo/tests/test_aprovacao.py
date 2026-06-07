"""
Testes da avaliação dos pareceres da revisão cega de uma Resenha.

- todas aprovar  -> resenha `revisada` (aguarda curador; NÃO publica)
- alguma ajustes -> resenha volta a `rascunho`
- alguma rejeitar-> resenha volta a `rascunho`
- faltam pareceres -> não decide
"""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.acervo.aprovacao import avaliar_apos_revisao_cega
from apps.acervo.models import Analise, Artigo, Resenha, Revisao
from apps.vocabulario.models import TermoVocabulario, Vocabulario

User = get_user_model()
pytestmark = pytest.mark.django_db


@pytest.fixture
def resenha_em_revisao(db):
    v = Vocabulario.objects.create(codigo="base", nome="Base")
    termo = TermoVocabulario.objects.create(vocabulario=v, nome="WoS")
    autor = User.objects.create_user(
        username="autor",
        email="a@u.edu.br",
        password="x",
        papel=User.Papel.ANALISTA,
    )
    artigo = Artigo.objects.create(
        doi="10.x/t",
        titulo="T",
        ano=2020,
        base_consulta=termo,
        link_acesso="https://e.org/t",
    )
    analise = Analise.objects.create(
        artigo=artigo,
        analista=autor,
        status=Analise.Status.PUBLICADA,
    )
    resenha = Resenha.objects.create(
        analise=analise,
        texto="R",
        status=Resenha.Status.EM_REVISAO,
    )
    revisores = [
        User.objects.create_user(
            username=f"r{i}",
            email=f"r{i}@u.edu.br",
            password="x",
            papel=User.Papel.ANALISTA,
            revisor_aprovado=True,
        )
        for i in range(2)
    ]
    prazo = timezone.now() + timedelta(days=21)
    revs = [
        Revisao.objects.create(resenha=resenha, revisor=revisores[i], prazo_em=prazo)
        for i in range(2)
    ]
    return resenha, revs


def _concluir(rev, parecer):
    # .update() evita disparar o signal de avaliação automática — aqui testamos
    # a função avaliar_apos_revisao_cega isoladamente (o disparo via signal é
    # coberto no fluxo e2e).
    Revisao.objects.filter(pk=rev.pk).update(parecer=parecer, concluido_em=timezone.now())


def test_todas_aprovar_marca_revisada(resenha_em_revisao):
    resenha, revs = resenha_em_revisao
    _concluir(revs[0], Revisao.Parecer.APROVAR)
    _concluir(revs[1], Revisao.Parecer.APROVAR)
    resultado = avaliar_apos_revisao_cega(resenha)
    assert resultado.decidida is True
    assert resultado.novo_status == Resenha.Status.REVISADA
    resenha.refresh_from_db()
    assert resenha.status == Resenha.Status.REVISADA
    assert resenha.publicada_em is None  # NÃO publica automaticamente


def test_um_ajustes_volta_para_rascunho(resenha_em_revisao):
    resenha, revs = resenha_em_revisao
    _concluir(revs[0], Revisao.Parecer.APROVAR)
    _concluir(revs[1], Revisao.Parecer.AJUSTES)
    resultado = avaliar_apos_revisao_cega(resenha)
    assert resultado.novo_status == Resenha.Status.RASCUNHO
    resenha.refresh_from_db()
    assert resenha.status == Resenha.Status.RASCUNHO


def test_um_rejeitar_volta_para_rascunho(resenha_em_revisao):
    resenha, revs = resenha_em_revisao
    _concluir(revs[0], Revisao.Parecer.REJEITAR)
    _concluir(revs[1], Revisao.Parecer.APROVAR)
    resultado = avaliar_apos_revisao_cega(resenha)
    assert resultado.novo_status == Resenha.Status.RASCUNHO


def test_faltam_pareceres_nao_decide(resenha_em_revisao):
    resenha, revs = resenha_em_revisao
    _concluir(revs[0], Revisao.Parecer.APROVAR)
    # revs[1] ainda pendente
    resultado = avaliar_apos_revisao_cega(resenha)
    assert resultado.decidida is False
    resenha.refresh_from_db()
    assert resenha.status == Resenha.Status.EM_REVISAO
