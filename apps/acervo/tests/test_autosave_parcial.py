"""Auto-save parcial da análise: cada aba salva só os seus campos, sem apagar as outras."""

import json

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.acervo.models import Analise, Artigo
from apps.vocabulario.models import TermoVocabulario, Vocabulario

User = get_user_model()
pytestmark = pytest.mark.django_db


@pytest.fixture
def analista(db):
    return User.objects.create_user(
        username="ana", email="ana@u.edu", password="x", papel=User.Papel.ANALISTA
    )


@pytest.fixture
def termo_epi(db):
    v = Vocabulario.objects.create(codigo="epistemologia", nome="Epistemologia")
    return TermoVocabulario.objects.create(vocabulario=v, nome="Construtivismo")


@pytest.fixture
def analise(db, analista):
    art = Artigo.objects.create(titulo="Obra", ano=2021)
    return Analise.objects.create(artigo=art, analista=analista, status=Analise.Status.RASCUNHO)


def _autosave(client, analise, data):
    resp = client.post(reverse("autosave_analise", args=[analise.pk]), data)
    return resp


def test_autosave_presenca_nao_apaga_estrutura(client, analista, analise, termo_epi):
    # Estrutura já preenchida (outra aba).
    analise.objeto = "meu objeto"
    analise.referenciais = "refs"
    analise.save()
    analise.epistemologia.set([termo_epi])

    client.force_login(analista)
    resp = _autosave(client, analise, {"presenca_titulo": "True", "pertinencia": "False"})
    assert resp.status_code == 200
    assert json.loads(resp.content)["ok"] is True

    analise.refresh_from_db()
    # Presença salva…
    assert analise.presenca_titulo is True
    assert analise.pertinencia is False
    # …e estrutura PRESERVADA (não foi apagada pelo POST parcial).
    assert analise.objeto == "meu objeto"
    assert analise.referenciais == "refs"
    assert list(analise.epistemologia.all()) == [termo_epi]


def test_autosave_estrutura_nao_apaga_presenca(client, analista, analise):
    analise.presenca_titulo = True
    analise.pertinencia = True
    analise.aspectos_relevantes = "relevante"
    analise.save()

    client.force_login(analista)
    resp = _autosave(client, analise, {"objeto": "novo objeto", "foco": "Neurociência"})
    assert resp.status_code == 200

    analise.refresh_from_db()
    assert analise.objeto == "novo objeto"
    assert analise.foco == "Neurociência"
    # Presença PRESERVADA.
    assert analise.presenca_titulo is True
    assert analise.pertinencia is True
    assert analise.aspectos_relevantes == "relevante"


def test_autosave_seta_m2m_quando_presente(client, analista, analise, termo_epi):
    client.force_login(analista)
    resp = _autosave(client, analise, {"epistemologia": [termo_epi.pk]})
    assert resp.status_code == 200
    analise.refresh_from_db()
    assert list(analise.epistemologia.all()) == [termo_epi]


def test_autosave_post_vazio_nao_altera(client, analista, analise):
    analise.objeto = "intacto"
    analise.save()
    client.force_login(analista)
    resp = _autosave(client, analise, {})
    assert resp.status_code == 200
    analise.refresh_from_db()
    assert analise.objeto == "intacto"


def test_autosave_salva_grande_area_do_artigo(client, analista, analise):
    client.force_login(analista)
    resp = _autosave(client, analise, {"area": "Interdisciplinar"})
    assert resp.status_code == 200
    analise.artigo.refresh_from_db()
    assert analise.artigo.area == "Interdisciplinar"


def test_autosave_retorna_faltantes_ao_vivo(client, analista, analise):
    client.force_login(analista)
    resp = _autosave(client, analise, {"pertinencia": "True"})
    data = json.loads(resp.content)
    assert data["ok"] is True
    # A lista reflete o estado atual (ainda faltam campos) — vira [] quando completa.
    assert isinstance(data["faltantes"], list)
    assert "Pertinência" not in data["faltantes"]  # acabou de responder
