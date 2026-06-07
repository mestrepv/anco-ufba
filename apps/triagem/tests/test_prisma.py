"""Fase 9.6 — contagens PRISMA, export e proveniência na página pública."""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.acervo.models import Analise, Artigo
from apps.triagem import prisma
from apps.triagem.models import Busca, ProtocoloTriagem, RegistroTriagem
from apps.triagem.promocao import promover_para_acervo
from apps.vocabulario.models import TermoVocabulario, Vocabulario

from .conftest import membro, turl

User = get_user_model()
pytestmark = pytest.mark.django_db


@pytest.fixture
def protocolo(db):
    return ProtocoloTriagem.ativo()


@pytest.fixture
def base_termo(db):
    v, _ = Vocabulario.objects.get_or_create(codigo="base", defaults={"nome": "Base"})
    return TermoVocabulario.objects.create(vocabulario=v, nome="Scopus")


@pytest.fixture
def analista(db):
    return membro(
        User.objects.create_user(
            username="ana", email="a@u.edu", password="x", papel=User.Papel.ANALISTA
        )
    )


def test_contagem_prisma(protocolo, base_termo):
    Busca.objects.create(protocolo=protocolo, base_consulta=base_termo, n_identificados=100)
    RegistroTriagem.objects.create(protocolo=protocolo, titulo="A", doi="10.1/a")
    RegistroTriagem.objects.create(protocolo=protocolo, titulo="B", doi="10.1/b", ja_no_acervo=True)
    RegistroTriagem.objects.create(
        protocolo=protocolo,
        titulo="C",
        doi="10.1/c",
        status=RegistroTriagem.Status.INCLUIDO,
    )
    RegistroTriagem.objects.create(
        protocolo=protocolo,
        titulo="D",
        doi="10.1/d",
        status=RegistroTriagem.Status.EXCLUIDO,
        motivo_exclusao="fora de escopo",
    )
    c = prisma.computar(protocolo)
    assert c.identificados_relatado == 100
    assert c.importados == 4
    assert c.ja_no_acervo == 1
    assert c.elegiveis == 3
    assert c.incluidos == 1
    assert c.excluidos == 1
    assert c.excluidos_por_motivo[0]["motivo_exclusao"] == "fora de escopo"


def test_prisma_view_e_exports(client, protocolo, analista, base_termo):
    Busca.objects.create(protocolo=protocolo, base_consulta=base_termo, n_identificados=10)
    client.force_login(analista)

    html = client.get(turl("triagem_prisma"))
    assert html.status_code == 200
    assert b"PRISMA" in html.content

    js = client.get(turl("triagem_prisma"), {"formato": "json"})
    assert js.status_code == 200
    assert js.json()["identificados_relatado"] == 10

    csv_resp = client.get(turl("triagem_prisma"), {"formato": "csv"})
    assert csv_resp.status_code == 200
    assert csv_resp["Content-Type"].startswith("text/csv")


def test_proveniencia_triagem_na_pagina_publica(client, protocolo, base_termo):
    autor = User.objects.create_user(
        username="au", email="au@u.edu", password="x", papel=User.Papel.ANALISTA
    )
    reg = RegistroTriagem.objects.create(
        protocolo=protocolo,
        titulo="Selecionado",
        doi="10.7/sel",
        status=RegistroTriagem.Status.INCLUIDO,
    )
    artigo = promover_para_acervo(reg)
    analise = Analise.objects.create(artigo=artigo, analista=autor, status=Analise.Status.PUBLICADA)
    resp = client.get(reverse("pagina_analise", args=[analise.pk]))
    assert resp.status_code == 200
    assert b"Selecionado por triagem" in resp.content


def test_sem_triagem_sem_selo(client, base_termo):
    autor = User.objects.create_user(
        username="au2", email="au2@u.edu", password="x", papel=User.Papel.ANALISTA
    )
    artigo = Artigo.objects.create(
        doi="10.7/normal", titulo="Comum", ano=2020, base_consulta=base_termo
    )
    analise = Analise.objects.create(artigo=artigo, analista=autor, status=Analise.Status.PUBLICADA)
    resp = client.get(reverse("pagina_analise", args=[analise.pk]))
    assert resp.status_code == 200
    assert b"Selecionado por triagem" not in resp.content
