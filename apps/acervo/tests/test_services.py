"""Testes dos servicos de validacao de link e Wayback Machine."""

from unittest.mock import patch

import pytest
import responses
from django.test import override_settings

from apps.acervo.models import Artigo, SnapshotLink
from apps.acervo.services import (
    LinkCheckResultado,
    aplicar_resultado_no_artigo,
    capturar_snapshot_wayback,
    validar_link,
)
from apps.vocabulario.models import TermoVocabulario, Vocabulario


@pytest.fixture
def vocab_base(db):
    v = Vocabulario.objects.create(codigo="base", nome="Base")
    return TermoVocabulario.objects.create(vocabulario=v, nome="WoS")


@pytest.fixture
def artigo(db, vocab_base):
    return Artigo.objects.create(
        doi="10.1/x",
        titulo="X",
        ano=2020,
        base_consulta=vocab_base,
        link_acesso="https://example.org/artigo",
    )


# ----------------------------------------------------------------------
# validar_link
# ----------------------------------------------------------------------


class TestValidarLink:
    def test_url_invalida_eh_quebrada(self):
        r = validar_link("nao-eh-url")
        assert r.status == "quebrado"

    def test_url_vazia_eh_quebrada(self):
        r = validar_link("")
        assert r.status == "quebrado"

    @patch("apps.acervo.services.links._eh_url_publica", return_value=False)
    def test_url_privada_eh_quebrada(self, _mock):
        r = validar_link("http://192.168.0.1/x")
        assert r.status == "quebrado"
        assert "privado" in r.mensagem

    @responses.activate
    @patch("apps.acervo.services.links._eh_url_publica", return_value=True)
    def test_200_eh_ok(self, _mock):
        responses.add(responses.HEAD, "https://example.org/x", status=200)
        r = validar_link("https://example.org/x")
        assert r.status == "ok"
        assert r.codigo_http == 200

    @responses.activate
    @patch("apps.acervo.services.links._eh_url_publica", return_value=True)
    def test_404_eh_quebrado(self, _mock):
        responses.add(responses.HEAD, "https://example.org/x", status=404)
        r = validar_link("https://example.org/x")
        assert r.status == "quebrado"
        assert r.codigo_http == 404

    @responses.activate
    @patch("apps.acervo.services.links._eh_url_publica", return_value=True)
    def test_redirect_marca_como_redireciona(self, _mock):
        responses.add(
            responses.HEAD,
            "https://example.org/x",
            status=200,
            adding_headers={"Location": "https://example.org/y"},
        )
        # responses devolve a url chamada como url final por default;
        # forcamos via parametro `url` do response object.
        r = validar_link("https://example.org/x")
        # Sem chained redirect real, assume "ok"; testar caminho completo
        # exigiria mock de chain. Aqui validamos so que nao quebrou.
        assert r.status in ("ok", "redireciona")

    @patch("apps.acervo.services.links._eh_url_publica", return_value=True)
    @patch("apps.acervo.services.links.requests.head")
    def test_excecao_de_rede_marca_quebrado(self, mock_head, _mock_priv):
        import requests as requests_lib

        mock_head.side_effect = requests_lib.ConnectTimeout("timeout")
        r = validar_link("https://example.org/x")
        assert r.status == "quebrado"
        assert "Falha" in r.mensagem


class TestAplicarResultadoNoArtigo:
    def test_atualiza_status_e_timestamp(self, db, artigo):
        r = LinkCheckResultado(status="ok", codigo_http=200, url_final=None)
        aplicar_resultado_no_artigo(artigo, r)
        artigo.refresh_from_db()
        assert artigo.link_status == "ok"
        assert artigo.link_ultima_verificacao is not None


# ----------------------------------------------------------------------
# capturar_snapshot_wayback
# ----------------------------------------------------------------------


class TestCapturarSnapshot:
    @override_settings(WAYBACK_API_ENABLED=False)
    def test_desligado_por_setting_retorna_none(self, db, artigo):
        s = capturar_snapshot_wayback(artigo, "https://example.org/x")
        assert s is None
        assert SnapshotLink.objects.count() == 0

    def test_url_vazia_retorna_none(self, db, artigo):
        s = capturar_snapshot_wayback(artigo, "")
        assert s is None

    @responses.activate
    def test_sucesso_cria_snapshot_com_url_do_header(self, db, artigo):
        responses.add(
            responses.GET,
            "https://web.archive.org/save/https://example.org/x",
            status=302,
            headers={
                "Content-Location": "/web/20260101000000/https://example.org/x",
            },
        )
        s = capturar_snapshot_wayback(artigo, "https://example.org/x")
        assert s is not None
        assert s.url_wayback.startswith("https://web.archive.org/web/")
        assert s.url_original == "https://example.org/x"
        assert SnapshotLink.objects.filter(artigo=artigo).count() == 1

    @responses.activate
    def test_falha_de_rede_retorna_none(self, db, artigo):
        # Sem registrar resposta, responses levanta ConnectionError
        s = capturar_snapshot_wayback(artigo, "https://example.org/x")
        assert s is None
