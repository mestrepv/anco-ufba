"""Fase 9.0 — wiring do app triagem e controle de acesso do painel placeholder."""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

User = get_user_model()
pytestmark = pytest.mark.django_db


@pytest.fixture
def leitor(db):
    return User.objects.create_user(
        username="leit", email="l@u.edu.br", password="x", papel=User.Papel.LEITOR
    )


@pytest.fixture
def analista(db):
    return User.objects.create_user(
        username="ana", email="a@u.edu.br", password="x", papel=User.Papel.ANALISTA
    )


def test_anonimo_redireciona_para_login(client):
    resp = client.get(reverse("triagem_painel"))
    assert resp.status_code == 302
    assert "/accounts/login/" in resp.headers["Location"]


def test_leitor_recebe_403(client, leitor):
    client.force_login(leitor)
    assert client.get(reverse("triagem_painel")).status_code == 403


def test_analista_ve_painel(client, analista):
    client.force_login(analista)
    resp = client.get(reverse("triagem_painel"))
    assert resp.status_code == 200
    assert b"Triagem" in resp.content
