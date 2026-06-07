"""Testes do M5: lookup_identificador_view (HTMX) + cadastrar_artigo reescrita."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse

from apps.acervo.models import Analise, Artigo
from apps.acervo.services._base import LookupResultado
from apps.vocabulario.models import TermoVocabulario, Vocabulario

User = get_user_model()

# DummyCache em dev → forçar LocMemCache para preservar comportamento entre lookup e check
_LOCMEM_CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "test-lookup-view",
    }
}


@pytest.fixture
def vocab_base(db):
    vocab, _ = Vocabulario.objects.get_or_create(codigo="base", defaults={"nome": "Base"})
    termo, _ = TermoVocabulario.objects.get_or_create(
        vocabulario=vocab, nome="Web of Science", defaults={"ativo": True}
    )
    return termo


@pytest.fixture
def analista(db):
    # is_staff: cadastro avulso é ação de curador/admin (política da Fase 10).
    return User.objects.create_user(
        username="ana",
        email="ana@usp.edu.br",
        password="x",
        is_staff=True,
        papel=User.Papel.ANALISTA,
    )


@pytest.fixture
def leitor(db):
    return User.objects.create_user(
        username="le", email="le@usp.edu.br", password="x", papel=User.Papel.LEITOR
    )


@pytest.fixture
def cliente_analista(client, analista):
    client.force_login(analista)
    return client


# ---------------------------------------------------------------------------
# lookup_identificador_view
# ---------------------------------------------------------------------------


class TestLookupView:
    def test_sem_id_retorna_estado_vazio(self, cliente_analista):
        resp = cliente_analista.get(reverse("lookup_identificador"))
        assert resp.status_code == 200
        assert b"Cole um DOI ou ISBN" in resp.content

    def test_doi_valido_renderiza_titulo(self, cliente_analista):
        fake = LookupResultado(
            encontrado=True,
            dados={
                "doi": "10.1016/x",
                "titulo": "Estudo de teste",
                "autores": ["Ana Silva"],
                "autores_str": "Ana Silva",
                "ano": 2024,
                "periodico": "Cogn Sci",
                "resumo": "",
            },
        )
        with patch("apps.acervo.views.lookup_doi", return_value=fake):
            resp = cliente_analista.get(reverse("lookup_identificador") + "?id=10.1016/x")
        assert resp.status_code == 200
        assert b"Estudo de teste" in resp.content
        assert b"Ana Silva" in resp.content

    def test_isbn_valido_chama_lookup_isbn(self, cliente_analista):
        fake = LookupResultado(
            encontrado=True,
            dados={
                "titulo": "Livro X",
                "autores": ["Autor X"],
                "autores_str": "Autor X",
                "ano": 2017,
                "isbn": "9780128038031",
                "tipo": "Livro",
                "resumo": "",
            },
        )
        with (
            patch("apps.acervo.views.lookup_isbn", return_value=fake) as mock_isbn,
            patch("apps.acervo.views.lookup_doi") as mock_doi,
        ):
            resp = cliente_analista.get(reverse("lookup_identificador") + "?id=9780128038031")
        assert resp.status_code == 200
        assert b"Livro X" in resp.content
        mock_isbn.assert_called_once()
        mock_doi.assert_not_called()

    def test_doi_inexistente_renderiza_aviso(self, cliente_analista):
        fake = LookupResultado(encontrado=False, erro="DOI não encontrado")
        with patch("apps.acervo.views.lookup_doi", return_value=fake):
            resp = cliente_analista.get(reverse("lookup_identificador") + "?id=10.9999/inexistente")
        assert resp.status_code == 200
        # Mensagem de fallback do template editorial
        assert b"manualmente" in resp.content

    def test_artigo_ja_no_acervo_sinaliza(self, cliente_analista, vocab_base):
        Artigo.objects.create(
            doi="10.1016/jaexiste",
            titulo="Já existe",
            ano=2023,
            base_consulta=vocab_base,
        )
        fake = LookupResultado(
            encontrado=True,
            dados={
                "doi": "10.1016/jaexiste",
                "titulo": "Já existe",
                "autores_str": "",
                "ano": 2023,
                "resumo": "",
            },
        )
        with patch("apps.acervo.views.lookup_doi", return_value=fake):
            resp = cliente_analista.get(reverse("lookup_identificador") + "?id=10.1016/jaexiste")
        assert resp.status_code == 200
        # Banner "arquivo existente" + flag em dados.ja_no_acervo para o Alpine
        assert b"arquivo existente" in resp.content
        assert b"j\xc3\xa1 existe no acervo" in resp.content
        assert b'"ja_no_acervo": true' in resp.content

    def test_lixo_textual_retorna_erro_amigavel(self, cliente_analista):
        # "Não consta" não é DOI nem ISBN → tipo desconhecido
        resp = cliente_analista.get(reverse("lookup_identificador") + "?id=Não consta")
        assert resp.status_code == 200
        assert b"reconheci" in resp.content or b"manualmente" in resp.content

    def test_leitor_recebe_403(self, client, leitor):
        client.force_login(leitor)
        resp = client.get(reverse("lookup_identificador") + "?id=10.1016/x")
        assert resp.status_code == 403

    def test_anonimo_redireciona_login(self, client):
        resp = client.get(reverse("lookup_identificador") + "?id=10.1016/x")
        assert resp.status_code == 302  # redirect to login


# ---------------------------------------------------------------------------
# cadastrar_artigo reescrita: aceita sem-DOI
# ---------------------------------------------------------------------------


class TestCadastrarArtigoSemDoi:
    @override_settings(WAYBACK_API_ENABLED=False)
    @patch("apps.acervo.views.validar_link")
    def test_post_com_isbn_cria_artigo_e_analise(
        self, mock_validar, cliente_analista, vocab_base, analista
    ):
        from apps.acervo.services.links import LinkCheckResultado

        mock_validar.return_value = LinkCheckResultado(status="ok", codigo_http=200, url_final=None)
        resp = cliente_analista.post(
            reverse("cadastrar_artigo"),
            data={
                "isbn": "9780128038031",
                "tipo_publicacao": "livro",
                "titulo": "Livro de cognição",
                "titulo_periodico": "",
                "ano": "2017",
                "volume": "",
                "numero": "",
                "pagina_inicial": "",
                "pagina_final": "",
                "area": "Ciências Humanas",
                "autores": "Hollnagel, E.",
                "vinculacao_institucional": "",
                "palavras_chaves": "",
                "resumo": "",
                "base_consulta": vocab_base.pk,
                "link_acesso": "https://example.org/livro",
                "link_acesso_alternativo": "",
                "artigo_pago": "",
                "acesso_aberto": "",
            },
        )
        assert resp.status_code == 302
        artigo = Artigo.objects.get(isbn="9780128038031")
        assert artigo.tipo_publicacao == "livro"
        assert Analise.objects.filter(artigo=artigo, analista=analista).exists()

    @override_settings(WAYBACK_API_ENABLED=False)
    @patch("apps.acervo.views.validar_link")
    def test_post_sem_doi_nem_isbn_gera_identificador_interno(
        self, mock_validar, cliente_analista, vocab_base, analista
    ):
        from apps.acervo.services.links import LinkCheckResultado

        mock_validar.return_value = LinkCheckResultado(status="ok", codigo_http=200, url_final=None)
        resp = cliente_analista.post(
            reverse("cadastrar_artigo"),
            data={
                "tipo_publicacao": "outro",
                "titulo": "Tese sem DOI",
                "titulo_periodico": "",
                "ano": "2020",
                "volume": "",
                "numero": "",
                "pagina_inicial": "",
                "pagina_final": "",
                "area": "Ciências Humanas",
                "autores": "Autor Y",
                "vinculacao_institucional": "",
                "palavras_chaves": "",
                "resumo": "",
                "base_consulta": vocab_base.pk,
                "link_acesso": "https://example.org/tese",
                "link_acesso_alternativo": "",
                "artigo_pago": "",
                "acesso_aberto": "",
            },
        )
        assert resp.status_code == 302
        artigo = Artigo.objects.get(titulo="Tese sem DOI")
        assert artigo.doi is None
        assert artigo.isbn is None
        assert artigo.identificador_interno is not None
        assert artigo.identificador_interno.startswith("legacy:")
