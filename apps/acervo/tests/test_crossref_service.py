"""Testes do serviço de lookup DOI via Crossref (apps.acervo.services.crossref)."""

from __future__ import annotations

import io
import json
import urllib.error
from unittest.mock import patch

import pytest
from django.core.cache import cache
from django.test import override_settings

from apps.acervo.services.crossref import (
    CACHE_PREFIXO,
    _limpa_abstract,
    lookup_doi,
    normalizar_doi,
)

# Settings dev usam DummyCache (sem persistência); tests forçam LocMemCache.
_LOCMEM_CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "test-crossref",
    }
}


@pytest.fixture(autouse=True)
def _limpa_cache_entre_testes():
    cache.clear()
    yield
    cache.clear()


def _resposta_fake(payload: dict, status: int = 200) -> io.BytesIO:
    """Simula urllib.urlopen retornando um JSON."""
    body = json.dumps(payload).encode("utf-8")

    class _Fake:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def read(self):
            return body

    return _Fake()


# ---------------------------------------------------------------------------
# normalizar_doi
# ---------------------------------------------------------------------------


class TestNormalizarDoi:
    def test_doi_canonico_passa_inalterado(self):
        assert normalizar_doi("10.1016/j.cogsys.2012.05.003") == "10.1016/j.cogsys.2012.05.003"

    def test_strip_https_doi_org(self):
        assert normalizar_doi("https://doi.org/10.1016/x") == "10.1016/x"

    def test_strip_http_dx_doi_org(self):
        assert normalizar_doi("http://dx.doi.org/10.1016/x") == "10.1016/x"

    def test_strip_prefixo_doi_textual(self):
        assert normalizar_doi("doi: 10.1016/x") == "10.1016/x"
        assert normalizar_doi("DOI:10.1016/x") == "10.1016/x"

    def test_strip_espacos(self):
        assert normalizar_doi("   10.1016/x   ") == "10.1016/x"


# ---------------------------------------------------------------------------
# _limpa_abstract
# ---------------------------------------------------------------------------


class TestLimpaAbstract:
    def test_remove_jats_p(self):
        raw = "<jats:p>Texto do resumo</jats:p>"
        assert _limpa_abstract(raw) == "Texto do resumo"

    def test_normaliza_espacos_multiplos(self):
        raw = "<jats:p>Texto  com   espacos</jats:p>"
        assert _limpa_abstract(raw) == "Texto com espacos"

    def test_vazio_retorna_vazio(self):
        assert _limpa_abstract("") == ""
        assert _limpa_abstract(None) == ""


# ---------------------------------------------------------------------------
# lookup_doi
# ---------------------------------------------------------------------------


class TestLookupDoi:
    def test_doi_valido_retorna_dados_normalizados(self):
        payload = {
            "message": {
                "DOI": "10.1016/x",
                "title": ["Estudo cognitivo"],
                "author": [
                    {"given": "Ana", "family": "Silva"},
                    {"given": "Bruno", "family": "Souza"},
                ],
                "container-title": ["Cognitive Science"],
                "publisher": "Elsevier",
                "type": "journal-article",
                "published": {"date-parts": [[2024, 3, 15]]},
                "volume": "48",
                "issue": "2",
                "page": "123-145",
                "ISSN": ["0364-0213"],
                "issn-type": [{"type": "print", "value": "0364-0213"}],
                "abstract": "<jats:p>Este artigo investiga…</jats:p>",
                "subject": ["Cognitive Science", "Psychology"],
                "URL": "https://doi.org/10.1016/x",
                "license": [{"URL": "https://creativecommons.org/licenses/by/4.0/"}],
                "is-referenced-by-count": 42,
            }
        }
        with patch(
            "apps.acervo.services.crossref.urllib.request.urlopen",
            return_value=_resposta_fake(payload),
        ):
            r = lookup_doi("10.1016/x")

        assert r.encontrado is True
        assert r.dados["doi"] == "10.1016/x"
        assert r.dados["titulo"] == "Estudo cognitivo"
        assert r.dados["autores"] == ["Ana Silva", "Bruno Souza"]
        assert r.dados["autores_str"] == "Ana Silva; Bruno Souza"
        assert r.dados["periodico"] == "Cognitive Science"
        assert r.dados["editora"] == "Elsevier"
        assert r.dados["tipo"] == "Artigo de periódico"
        assert r.dados["ano"] == 2024
        assert r.dados["volume"] == "48"
        assert r.dados["resumo"] == "Este artigo investiga…"
        assert r.dados["citacoes_crossref"] == 42

    def test_doi_inexistente_retorna_404(self):
        erro_404 = urllib.error.HTTPError(url="x", code=404, msg="Not Found", hdrs=None, fp=None)
        with patch(
            "apps.acervo.services.crossref.urllib.request.urlopen",
            side_effect=erro_404,
        ):
            r = lookup_doi("10.9999/inexistente")

        assert r.encontrado is False
        assert "não encontrado" in r.erro

    def test_timeout_retorna_erro_sem_cachear(self):
        with patch(
            "apps.acervo.services.crossref.urllib.request.urlopen",
            side_effect=TimeoutError("connect timed out"),
        ):
            r = lookup_doi("10.1016/timeout")

        assert r.encontrado is False
        assert "timeout" in r.erro.lower()
        # Cache não deve ter o resultado de timeout
        assert cache.get(CACHE_PREFIXO + "10.1016/timeout") is None

    def test_doi_com_prefixo_url_normaliza(self):
        payload = {"message": {"DOI": "10.1016/x", "title": ["t"], "author": []}}
        with patch(
            "apps.acervo.services.crossref.urllib.request.urlopen",
            return_value=_resposta_fake(payload),
        ):
            r = lookup_doi("https://doi.org/10.1016/x")
        assert r.encontrado is True

    def test_doi_invalido_nao_chama_api(self):
        with patch("apps.acervo.services.crossref.urllib.request.urlopen") as mock_urlopen:
            r = lookup_doi("nao-é-um-doi")
        assert r.encontrado is False
        assert "inválido" in r.erro
        mock_urlopen.assert_not_called()

    @override_settings(CACHES=_LOCMEM_CACHES)
    def test_segunda_chamada_usa_cache(self):
        cache.clear()
        payload = {"message": {"DOI": "10.1016/cache", "title": ["t"], "author": []}}
        with patch(
            "apps.acervo.services.crossref.urllib.request.urlopen",
            return_value=_resposta_fake(payload),
        ) as mock_urlopen:
            lookup_doi("10.1016/cache")
            lookup_doi("10.1016/cache")  # deve vir do cache

        assert mock_urlopen.call_count == 1
