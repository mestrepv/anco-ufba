"""Fase 9.0 — wiring do app triagem e controle de acesso do painel.
Fase 12 — escopo por projeto na URL + membership."""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.triagem.models import ProtocoloTriagem

from .conftest import inscrever

User = get_user_model()
pytestmark = pytest.mark.django_db


@pytest.fixture
def protocolo(db):
    return ProtocoloTriagem.ativo()


@pytest.fixture
def leitor(db):
    return User.objects.create_user(
        username="leit", email="l@u.edu.br", password="x", papel=User.Papel.LEITOR
    )


@pytest.fixture
def analista(db, protocolo):
    u = User.objects.create_user(
        username="ana", email="a@u.edu.br", password="x", papel=User.Papel.ANALISTA
    )
    inscrever(protocolo, u)
    return u


def test_anonimo_redireciona_para_login(client, protocolo):
    resp = client.get(reverse("triagem_painel", args=[protocolo.slug]))
    assert resp.status_code == 302
    assert "/accounts/login/" in resp.headers["Location"]


def test_leitor_recebe_403(client, leitor, protocolo):
    client.force_login(leitor)
    assert client.get(reverse("triagem_painel", args=[protocolo.slug])).status_code == 403


def test_analista_ve_painel(client, analista, protocolo):
    client.force_login(analista)
    resp = client.get(reverse("triagem_painel", args=[protocolo.slug]))
    assert resp.status_code == 200
    assert b"Triagem" in resp.content


def test_lista_projetos_do_membro(client, analista):
    client.force_login(analista)
    resp = client.get(reverse("triagem_projetos"))
    assert resp.status_code == 200
    assert b"Projetos" in resp.content
