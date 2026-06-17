"""Fase 10.4 — só triados na análise: bloqueio do avulso + ponte 'a analisar'."""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.acervo.models import Analise, Artigo
from apps.triagem.models import ProtocoloTriagem, RegistroTriagem
from apps.triagem.promocao import promover_para_acervo
from apps.vocabulario.models import TermoVocabulario, Vocabulario

from .conftest import turl

User = get_user_model()
pytestmark = pytest.mark.django_db


@pytest.fixture
def protocolo(db):
    return ProtocoloTriagem.ativo()


@pytest.fixture
def vocab(db):
    v = Vocabulario.objects.create(codigo="base", nome="Base")
    return TermoVocabulario.objects.create(vocabulario=v, nome="WoS")


@pytest.fixture
def analista(db):
    return User.objects.create_user(
        username="ana", email="a@u.edu", password="x", papel=User.Papel.ANALISTA
    )


@pytest.fixture
def curador(db):
    return User.objects.create_user(
        username="cur",
        email="c@u.edu",
        password="x",
        papel=User.Papel.CURADOR,
        is_staff=True,
    )


def _artigo_incluido(protocolo, doi="10.3/incl"):
    reg = RegistroTriagem.objects.create(
        protocolo=protocolo,
        titulo="Incluído",
        doi=doi,
        ano=2022,
        status=RegistroTriagem.Status.INCLUIDO,
    )
    return promover_para_acervo(reg)


def test_analista_cria_artigo_avulso(client, analista, vocab):
    """Inclusão avulsa (Revisão ANCO): o analista cria o próprio artigo."""
    client.force_login(analista)
    resp = client.post(
        reverse("cadastrar_artigo"),
        data={
            "doi": "10.123/novo",
            "titulo": "Tentativa",
            "ano": "2023",
            "area": "Psicologia",
            "base_consulta": vocab.pk,
            "link_acesso": "https://e.org/x",
        },
    )
    assert resp.status_code == 302
    assert Artigo.objects.filter(doi="10.123/novo").exists()


def test_curador_cria_artigo_avulso(client, curador, vocab):
    client.force_login(curador)
    resp = client.post(
        reverse("cadastrar_artigo"),
        data={
            "doi": "10.123/cur",
            "titulo": "Avulso curador",
            "ano": "2023",
            "area": "Psicologia",
            "base_consulta": vocab.pk,
            "link_acesso": "https://e.org/c",
        },
    )
    assert resp.status_code == 302
    assert Artigo.objects.filter(doi="10.123/cur").exists()


def test_a_analisar_lista_incluidos(client, protocolo, analista):
    artigo = _artigo_incluido(protocolo)
    client.force_login(analista)
    resp = client.get(turl("triagem_a_analisar"))
    assert resp.status_code == 200
    assert artigo in list(resp.context["pagina"].object_list)


def test_a_analisar_ignora_projeto_arquivado(client, analista):
    """Incluídos de projeto PRISMA arquivado não vazam para a fila (regressão:
    registros legados de projetos ANCO migrados para apps/anco e arquivados)."""
    arquivado = ProtocoloTriagem.objects.create(titulo="Arquivado", arquivado=True)
    artigo = _artigo_incluido(arquivado, doi="10.3/arquivado")
    client.force_login(analista)
    resp = client.get(turl("triagem_a_analisar"))
    assert resp.status_code == 200
    assert artigo not in list(resp.context["pagina"].object_list)


def test_a_analisar_oculta_ja_analisados(client, protocolo, analista):
    artigo = _artigo_incluido(protocolo, doi="10.3/ja")
    Analise.objects.create(artigo=artigo, analista=analista, status=Analise.Status.RASCUNHO)
    client.force_login(analista)
    resp = client.get(turl("triagem_a_analisar"))
    assert artigo not in list(resp.context["pagina"].object_list)


def test_analista_reaproveita_incluido(client, protocolo, analista):
    """Reuso de artigo já incluído na triagem é permitido ao analista."""
    artigo = _artigo_incluido(protocolo, doi="10.3/reuse")
    client.force_login(analista)
    resp = client.post(reverse("cadastrar_artigo"), data={"doi": "10.3/reuse"})
    assert resp.status_code == 302
    assert "editar" in resp.headers["Location"]
    assert Analise.objects.filter(artigo=artigo, analista=analista).exists()
