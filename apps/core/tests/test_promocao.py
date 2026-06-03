"""Testes do fluxo de solicitação/promoção a analista (via PerfilForm)."""

import pytest
from django.contrib.auth import get_user_model

from apps.core.forms import PerfilForm
from apps.core.models import SolicitacaoCadastro

User = get_user_model()
pytestmark = pytest.mark.django_db


@pytest.fixture
def leitor(db):
    return User.objects.create_user(
        username="leitor1", email="leitor@usp.edu.br", password="senha-teste",
        papel=User.Papel.LEITOR,
    )


def _dados_perfil(**extra):
    base = {
        "nome_exibicao": "Leitor Um",
        "vinculo_institucional": "",
        "orcid": "",
        "lattes_url": "",
    }
    base.update(extra)
    return base


def test_marcar_analista_cria_solicitacao_pendente(leitor):
    form = PerfilForm(data=_dados_perfil(quer_ser_analista=True), instance=leitor)
    assert form.is_valid(), form.errors
    form.save()
    assert leitor.solicitacoes.filter(
        tipo=SolicitacaoCadastro.Tipo.ANALISTA,
        status=SolicitacaoCadastro.Status.PENDENTE,
    ).exists()


def test_sem_marcar_nao_cria_solicitacao(leitor):
    form = PerfilForm(data=_dados_perfil(), instance=leitor)
    assert form.is_valid(), form.errors
    form.save()
    assert not leitor.solicitacoes.exists()


def test_aprovar_solicitacao_promove_a_analista(leitor):
    form = PerfilForm(data=_dados_perfil(quer_ser_analista=True), instance=leitor)
    assert form.is_valid(), form.errors
    form.save()
    sol = leitor.solicitacoes.get(tipo=SolicitacaoCadastro.Tipo.ANALISTA)

    sol.status = SolicitacaoCadastro.Status.APROVADA
    sol.save()  # signal promove o usuário

    leitor.refresh_from_db()
    assert leitor.papel == User.Papel.ANALISTA
