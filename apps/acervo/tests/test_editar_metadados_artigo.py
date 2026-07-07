"""Editar metadados do artigo da análise (completar campos da importação)."""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.acervo.models import Analise, Artigo
from apps.vocabulario.models import TermoVocabulario, Vocabulario

User = get_user_model()
pytestmark = pytest.mark.django_db


@pytest.fixture
def base(db):
    v, _ = Vocabulario.objects.get_or_create(codigo="base", defaults={"nome": "Base"})
    return TermoVocabulario.objects.create(vocabulario=v, nome="Scopus")


@pytest.fixture
def analista(db):
    return User.objects.create_user(
        username="ana", email="ana@u.edu", password="x", papel=User.Papel.ANALISTA
    )


@pytest.fixture
def artigo(db, base):
    return Artigo.objects.create(
        titulo="Obra importada",
        ano=2023,
        autores="Silva, A.",
        area="Interdisciplinar",
        resumo="",  # veio vazio da importação
        palavras_chaves="",
        base_consulta=base,
        link_acesso="https://ex.org/a",
        doi="10.1/x",
    )


@pytest.fixture
def analise(db, artigo, analista):
    return Analise.objects.create(artigo=artigo, analista=analista, status=Analise.Status.RASCUNHO)


def _url(analise):
    return reverse("editar_metadados_artigo", args=[analise.pk])


def _payload(artigo, **over):
    dados = {
        "doi": artigo.doi or "",
        "isbn": "",
        "tipo_publicacao": "artigo",
        "titulo": artigo.titulo,
        "titulo_periodico": "Cogn Sci",
        "idioma": "en",
        "ano": artigo.ano,
        "volume": "",
        "numero": "",
        "pagina_inicial": "",
        "pagina_final": "",
        "area": "Interdisciplinar",
        "area_outra": "",
        "autores": "Silva, A.; Souza, B.",
        "vinculacao_institucional": "",
        "palavras_chaves": "cognição; equipe",
        "resumo": "Resumo agora preenchido pelo analista.",
        "base_consulta": artigo.base_consulta_id,
        "link_acesso": artigo.link_acesso,
        "link_acesso_alternativo": "",
    }
    dados.update(over)
    return dados


def test_autor_edita_campos_faltantes(client, analise, artigo, analista):
    client.force_login(analista)
    resp = client.post(_url(analise), _payload(artigo))
    assert resp.status_code == 302
    assert resp["Location"] == reverse("editar_analise", args=[analise.pk])
    artigo.refresh_from_db()
    assert artigo.resumo == "Resumo agora preenchido pelo analista."
    assert "equipe" in artigo.palavras_chaves


def test_botao_aparece_no_editor(client, analise, analista):
    client.force_login(analista)
    resp = client.get(reverse("editar_analise", args=[analise.pk]))
    assert reverse("editar_metadados_artigo", args=[analise.pk]).encode() in resp.content
    assert b"Editar dados do artigo" in resp.content


def test_outro_analista_nao_edita(client, analise, artigo):
    outro = User.objects.create_user(
        username="o", email="o@u.edu", password="x", papel=User.Papel.ANALISTA
    )
    client.force_login(outro)
    resp = client.post(_url(analise), _payload(artigo))
    assert resp.status_code == 403


def test_legado_bloqueado(client, artigo, analista):
    artigo.eh_legado = True
    artigo.save(update_fields=["eh_legado"])
    analise = Analise.objects.create(
        artigo=artigo, analista=analista, status=Analise.Status.RASCUNHO
    )
    client.force_login(analista)
    resp = client.get(_url(analise))
    assert resp.status_code == 403


def test_espelha_no_corpus(client, analise, artigo, analista):
    from apps.anco.models import ItemCorpus, ProjetoANCO

    proj = ProjetoANCO.objects.create(nome="P", slug="p-x")
    item = ItemCorpus.objects.create(
        projeto=proj, titulo="antigo", identificador="k1", artigo=artigo, resumo=""
    )
    client.force_login(analista)
    client.post(_url(analise), _payload(artigo))
    item.refresh_from_db()
    assert item.resumo == "Resumo agora preenchido pelo analista."
    assert item.titulo == artigo.titulo
