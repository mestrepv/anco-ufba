"""Fase B: rotas antigas de projeto ANCO no /triagem/ redirecionam (301) ao /anco/."""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.anco.models import ProjetoANCO
from apps.triagem.models import ProjetoMembro, ProtocoloTriagem

User = get_user_model()
pytestmark = pytest.mark.django_db


def test_triagem_painel_anco_redireciona_para_anco():
    proto = ProtocoloTriagem.objects.create(
        nome="Piloto", slug="piloto-x", modo=ProtocoloTriagem.Modo.ANCO
    )
    ProjetoANCO.objects.create(nome="Piloto", slug="piloto-x")  # destino migrado
    u = User.objects.create_user(username="m", email="m@u.edu", password="x")
    ProjetoMembro.objects.create(projeto=proto, usuario=u, papel="curador")
    client_login = u
    from django.test import Client

    c = Client()
    c.force_login(client_login)
    resp = c.get(reverse("triagem_painel", args=["piloto-x"]))
    assert resp.status_code == 301
    assert resp.url == reverse("anco_painel", args=["piloto-x"])


def test_projeto_rigoroso_nao_redireciona():
    proto = ProtocoloTriagem.objects.create(
        nome="Rig", slug="rig-x", modo=ProtocoloTriagem.Modo.RIGOROSO
    )
    u = User.objects.create_user(
        username="a", email="a@u.edu", password="x", papel=User.Papel.ANALISTA
    )
    ProjetoMembro.objects.create(projeto=proto, usuario=u, papel="analista")
    from django.test import Client

    c = Client()
    c.force_login(u)
    resp = c.get(reverse("triagem_painel", args=["rig-x"]))
    assert resp.status_code == 200  # PRISMA segue no triagem
