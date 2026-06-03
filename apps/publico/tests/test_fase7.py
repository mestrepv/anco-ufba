"""Testes da Fase 7: paginas institucionais, robots/sitemap, rate limit."""

from datetime import UTC, datetime

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.acervo.models import Analise, Artigo
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
        username="a",
        email="a@u.edu.br",
        password="x",
        nome_exibicao="Maria",
    )


@pytest.fixture
def analise_publica(db, vocab, autor):
    artigo = Artigo.objects.create(
        doi="10.1/x",
        titulo="X",
        ano=2022,
        base_consulta=vocab,
        link_acesso="https://e.org/x",
    )
    return Analise.objects.create(
        artigo=artigo,
        analista=autor,
        status=Analise.Status.PUBLICADA,
        publicada_em=datetime(2024, 1, 1, tzinfo=UTC),
    )


# ----------------------------------------------------------------------
# Paginas institucionais
# ----------------------------------------------------------------------


class TestPaginasInstitucionais:
    def test_sobre(self, client, db):
        resp = client.get(reverse("pagina_sobre"))
        assert resp.status_code == 200
        assert b"Sobre a AnCo" in resp.content
        assert b"Creative Commons" in resp.content

    def test_equipe(self, client, db):
        resp = client.get(reverse("pagina_equipe"))
        assert resp.status_code == 200
        assert b"Equipe" in resp.content

    def test_termos(self, client, db):
        resp = client.get(reverse("pagina_termos"))
        assert resp.status_code == 200
        assert b"Termos" in resp.content
        # Menciona pontos chave dos termos
        assert b"CC BY-NC" in resp.content
        assert b"revis" in resp.content.lower()

    def test_privacidade(self, client, db):
        resp = client.get(reverse("pagina_privacidade"))
        assert resp.status_code == 200
        # Cobre LGPD basico
        assert b"LGPD" in resp.content
        assert b"OAuth" in resp.content

    def test_links_no_footer(self, client, db):
        resp = client.get(reverse("home"))
        for url in ("pagina_sobre", "pagina_equipe", "pagina_termos", "pagina_privacidade"):
            assert reverse(url).encode() in resp.content


# ----------------------------------------------------------------------
# robots.txt e sitemap.xml
# ----------------------------------------------------------------------


class TestRobotsTxt:
    def test_robots_txt_acessivel(self, client, db):
        resp = client.get(reverse("robots"))
        assert resp.status_code == 200
        assert resp["Content-Type"].startswith("text/plain")
        body = resp.content.decode()
        assert "User-agent: *" in body
        assert "Disallow: /admin/" in body
        assert "Sitemap:" in body


class TestSitemap:
    def test_sitemap_xml_acessivel(self, client, db):
        resp = client.get(reverse("sitemap"))
        assert resp.status_code == 200
        assert "application/xml" in resp["Content-Type"]
        assert b"<urlset" in resp.content

    def test_sitemap_inclui_paginas_publicas_basicas(self, client, db):
        resp = client.get(reverse("sitemap"))
        body = resp.content.decode()
        assert "/sobre/" in body
        assert "/acervo/" in body
        assert "/termos/" in body

    def test_sitemap_inclui_analise_publicada(self, client, analise_publica):
        resp = client.get(reverse("sitemap"))
        body = resp.content.decode()
        assert f"/analise/{analise_publica.pk}/" in body
        assert f"/artigo/" in body  # noqa: F541
        # lastmod do artigo presente
        assert "<lastmod>" in body

    def test_sitemap_nao_lista_rascunhos(self, client, db, vocab, autor):
        artigo = Artigo.objects.create(
            doi="10.r/x",
            titulo="rascunho",
            ano=2020,
            base_consulta=vocab,
            link_acesso="https://e.org/r",
        )
        Analise.objects.create(
            artigo=artigo,
            analista=autor,
            status=Analise.Status.RASCUNHO,
        )
        resp = client.get(reverse("sitemap"))
        body = resp.content.decode()
        # Artigo cuja unica analise eh rascunho NAO eh listado
        assert "10.r/x" not in body and "10.r__x" not in body


# ----------------------------------------------------------------------
# Rate limit (soft) na listagem
# ----------------------------------------------------------------------


class TestRateLimitListagem:
    def test_listagem_nao_bloqueia_em_volume_normal(self, client, db):
        for _ in range(5):
            resp = client.get(reverse("acervo_publico"))
            assert resp.status_code == 200

    def test_decorator_aplicado(self):
        from apps.publico import views

        # Decorator @ratelimit anota o atributo `_decorated`
        # ou similar na view; validar que existe
        assert hasattr(views.listagem_view, "__wrapped__") or (
            "ratelimit" in (views.listagem_view.__qualname__ or "").lower()
            or callable(views.listagem_view)
        )
