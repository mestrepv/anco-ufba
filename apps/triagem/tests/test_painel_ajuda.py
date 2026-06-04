"""Redesenho do painel + página de ajuda da triagem."""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.triagem.models import ProtocoloTriagem, RegistroTriagem
from apps.triagem.promocao import promover_para_acervo

User = get_user_model()
pytestmark = pytest.mark.django_db


@pytest.fixture
def protocolo(db):
    return ProtocoloTriagem.ativo()


@pytest.fixture
def analista(db):
    return User.objects.create_user(
        username="ana", email="a@u.edu", password="x", papel=User.Papel.ANALISTA
    )


@pytest.fixture
def leitor(db):
    return User.objects.create_user(
        username="le", email="le@u.edu", password="x", papel=User.Papel.LEITOR
    )


def test_ajuda_renderiza_com_criterios(client, protocolo, analista):
    client.force_login(analista)
    resp = client.get(reverse("triagem_ajuda"))
    assert resp.status_code == 200
    assert b"Como funciona a triagem" in resp.content
    assert b"PRISMA-ScR" in resp.content


def test_ajuda_exige_analista(client, leitor):
    client.force_login(leitor)
    assert client.get(reverse("triagem_ajuda")).status_code == 403


def test_painel_mostra_fluxo_e_proximo_passo(client, analista):
    client.force_login(analista)
    resp = client.get(reverse("painel"))
    assert resp.status_code == 200
    assert b"O fluxo da triagem" in resp.content
    assert "Próximo passo".encode() in resp.content
    assert b"Importar base" in resp.content  # etapa clicável do mapa


def test_painel_conta_a_analisar(client, protocolo, analista):
    reg = RegistroTriagem.objects.create(
        protocolo=protocolo, titulo="Incluído", doi="10.9/x",
        status=RegistroTriagem.Status.INCLUIDO,
    )
    promover_para_acervo(reg)
    client.force_login(analista)
    resp = client.get(reverse("painel"))
    assert resp.context["n_a_analisar"] == 1
    # badge na etapa "A analisar" + hero apontando para análise
    assert b"A analisar" in resp.content
    assert resp.context["proxima"]["href"].endswith("/a-analisar/")


def test_painel_leitor_sem_secao_triagem(client, leitor):
    client.force_login(leitor)
    resp = client.get(reverse("painel"))
    assert resp.status_code == 200
    assert b"O fluxo da triagem" not in resp.content
