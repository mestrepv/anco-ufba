"""Redesenho do painel + página de ajuda da triagem."""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.triagem.models import ProtocoloTriagem, RegistroTriagem
from apps.triagem.promocao import promover_para_acervo

from .conftest import membro, turl

User = get_user_model()
pytestmark = pytest.mark.django_db


@pytest.fixture
def protocolo(db):
    return ProtocoloTriagem.ativo()


@pytest.fixture
def analista(db):
    return membro(
        User.objects.create_user(
            username="ana", email="a@u.edu", password="x", papel=User.Papel.ANALISTA
        )
    )


@pytest.fixture
def leitor(db):
    return User.objects.create_user(
        username="le", email="le@u.edu", password="x", papel=User.Papel.LEITOR
    )


def test_ajuda_renderiza_com_criterios(client, protocolo, analista):
    client.force_login(analista)
    resp = client.get(turl("triagem_ajuda"))
    assert resp.status_code == 200
    assert b"Como funciona a triagem" in resp.content
    assert b"PRISMA-ScR" in resp.content


def test_ajuda_exige_analista(client, leitor):
    client.force_login(leitor)
    assert client.get(turl("triagem_ajuda")).status_code == 403


def test_painel_nao_mostra_prisma(client, protocolo, analista):
    # PRISMA-ScR saiu do painel (vive em /triagem/). Membro de um projeto de
    # triagem NÃO vê o projeto nem menção a PRISMA no /painel/ (agora ANCO-only).
    client.force_login(analista)
    resp = client.get(reverse("painel"))
    assert resp.status_code == 200
    assert reverse("triagem_painel", args=[protocolo.slug]).encode() not in resp.content
    assert b"PRISMA-ScR" not in resp.content
    assert "Próximo passo".encode() not in resp.content  # sem ANCO → sem hero


def test_painel_mostra_aba_anco(client, analista):
    # Membro de um projeto ANCO vê a aba "Revisão ANCO" e o link para /anco/.
    from apps.anco.models import MembroANCO, ProjetoANCO

    pa = ProjetoANCO.objects.create(nome="Piloto ANCO")
    MembroANCO.objects.create(projeto=pa, usuario=analista, papel=MembroANCO.Papel.ANALISTA)
    analista.pode_anco = True
    analista.save(update_fields=["pode_anco"])
    client.force_login(analista)
    resp = client.get(reverse("painel"))
    assert resp.status_code == 200
    assert "Revisão ANCO".encode() in resp.content
    assert reverse("anco_painel", args=[pa.slug]).encode() in resp.content


def test_painel_ignora_tarefa_de_triagem_no_proximo_passo(client, protocolo, analista):
    # Mesmo com artigo vindo da triagem, o painel (ANCO-exclusivo) NÃO gera um
    # "Próximo passo" de triagem apontando para /a-analisar/. Essa tarefa vive
    # agora só em /triagem/.
    reg = RegistroTriagem.objects.create(
        protocolo=protocolo,
        titulo="Incluído",
        doi="10.9/x",
        status=RegistroTriagem.Status.INCLUIDO,
    )
    promover_para_acervo(reg)
    client.force_login(analista)
    resp = client.get(reverse("painel"))
    prox = resp.context["proxima"]
    assert prox is None or not prox["href"].endswith("/a-analisar/")


def test_painel_leitor_sem_secao_triagem(client, leitor):
    client.force_login(leitor)
    resp = client.get(reverse("painel"))
    assert resp.status_code == 200
    assert b"Suas revis" not in resp.content
