"""Testes do JSON-LD (schema.org) do acervo publico."""

import json
from datetime import UTC, datetime

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.acervo.models import Analise, Artigo
from apps.publico.schema import jsonld, schema_analise, schema_artigo
from apps.publico.services import doi_to_slug
from apps.vocabulario.models import TermoVocabulario, Vocabulario

User = get_user_model()
pytestmark = pytest.mark.django_db


@pytest.fixture
def vocab(db):
    v = Vocabulario.objects.create(codigo="base", nome="Base")
    return TermoVocabulario.objects.create(vocabulario=v, nome="WoS")


@pytest.fixture
def autor(db):
    return User.objects.create_user(
        username="autor",
        email="a@u.edu.br",
        password="x",
        nome_exibicao="Maria da Silva",
    )


@pytest.fixture
def artigo(db, vocab):
    return Artigo.objects.create(
        doi="10.1234/teste",
        titulo="Cognição em redes",
        titulo_periodico="Revista X",
        ano=2022,
        base_consulta=vocab,
        link_acesso="https://example.org/x",
        autores="Maria da Silva; João Pereira",
        resumo="Resumo do artigo.",
        acesso_aberto=True,
    )


@pytest.fixture
def analise(db, artigo, autor):
    return Analise.objects.create(
        artigo=artigo,
        analista=autor,
        status=Analise.Status.PUBLICADA,
        publicada_em=datetime(2024, 5, 10, tzinfo=UTC),
        resenha_critica="Texto critico autoral.",
    )


# ----------------------------------------------------------------------
# schema_artigo
# ----------------------------------------------------------------------


class TestSchemaArtigo:
    def test_tipo_e_contexto(self, artigo):
        s = schema_artigo(artigo)
        assert s["@context"] == "https://schema.org"
        assert s["@type"] == "ScholarlyArticle"

    def test_doi_canonico_vira_sameAs_e_identifier(self, artigo):
        s = schema_artigo(artigo)
        assert s["sameAs"] == "https://doi.org/10.1234/teste"
        assert s["identifier"]["propertyID"] == "DOI"
        assert s["identifier"]["value"] == "10.1234/teste"

    def test_doi_legacy_nao_gera_doi_org(self, db, vocab):
        a = Artigo.objects.create(
            doi="legacy:abc123",
            titulo="X",
            ano=2020,
            base_consulta=vocab,
            link_acesso="https://e.org/x",
        )
        s = schema_artigo(a)
        assert "sameAs" not in s
        assert "identifier" not in s

    def test_autores_separados_por_ponto_virgula(self, artigo):
        s = schema_artigo(artigo)
        nomes = [a["name"] for a in s["author"]]
        assert "Maria da Silva" in nomes
        assert "João Pereira" in nomes

    def test_acesso_aberto_marcado(self, artigo):
        s = schema_artigo(artigo)
        assert s["isAccessibleForFree"] is True


# ----------------------------------------------------------------------
# schema_analise
# ----------------------------------------------------------------------


class TestSchemaAnalise:
    def test_tipo_review(self, analise):
        s = schema_analise(analise)
        assert s["@type"] == "Review"

    def test_url_estavel(self, analise):
        s = schema_analise(analise)
        assert f"/analise/{analise.pk}/" in s["url"]
        assert s["@id"] == s["url"]

    def test_autor_visivel_no_review(self, analise):
        s = schema_analise(analise)
        assert s["author"]["name"] == "Maria da Silva"

    def test_itemReviewed_eh_o_artigo(self, analise):
        s = schema_analise(analise)
        assert s["itemReviewed"]["@type"] == "ScholarlyArticle"
        assert s["itemReviewed"]["name"] == "Cognição em redes"

    def test_licenca_cc_by_nc(self, analise):
        s = schema_analise(analise)
        assert "creativecommons.org/licenses/by-nc/4.0/" in s["license"]

    def test_resenha_no_reviewBody(self, analise):
        s = schema_analise(analise)
        assert s["reviewBody"] == "Texto critico autoral."

    def test_sem_resenha_nao_inclui_reviewBody(self, db, artigo, autor):
        a = Analise.objects.create(
            artigo=artigo,
            analista=autor,
            status=Analise.Status.PUBLICADA,
            publicada_em=datetime(2024, 5, 10, tzinfo=UTC),
        )
        s = schema_analise(a)
        assert "reviewBody" not in s


# ----------------------------------------------------------------------
# jsonld helper
# ----------------------------------------------------------------------


class TestJsonldHelper:
    def test_serializa_para_json_valido(self, analise):
        s = jsonld(schema_analise(analise))
        # round-trip JSON
        parsed = json.loads(s)
        assert parsed["@type"] == "Review"

    def test_caracteres_unicode_preservados(self, analise):
        s = jsonld(schema_analise(analise))
        assert "Cognição" in s


# ----------------------------------------------------------------------
# Renderizacao no template
# ----------------------------------------------------------------------


class TestJsonldNaPagina:
    def test_pagina_artigo_inclui_jsonld(self, client, artigo, analise):
        slug = doi_to_slug(artigo.doi)
        resp = client.get(reverse("pagina_artigo", args=[slug]))
        assert resp.status_code == 200
        assert b"application/ld+json" in resp.content
        assert b'"ScholarlyArticle"' in resp.content

    def test_pagina_analise_inclui_jsonld_review(self, client, analise):
        resp = client.get(reverse("pagina_analise", args=[analise.pk]))
        assert resp.status_code == 200
        assert b"application/ld+json" in resp.content
        assert b'"Review"' in resp.content
        assert b'"itemReviewed"' in resp.content
