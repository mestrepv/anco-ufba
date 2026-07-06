"""Serviço OpenAlex — reconstrução do abstract e lookup por DOI."""

import io
import json
import urllib.error
from unittest.mock import patch

import pytest
from django.core.cache import cache

from apps.acervo.services.openalex import _reconstruir_abstract, abstract_por_doi


def _resposta_fake(payload: dict):
    return io.BytesIO(json.dumps(payload).encode())


@pytest.fixture(autouse=True)
def _limpa_cache():
    cache.clear()
    yield
    cache.clear()


class TestReconstruirAbstract:
    def test_reconstroi_na_ordem_das_posicoes(self):
        indice = {"análise": [0, 3], "cognitiva": [1], "é": [2]}
        assert _reconstruir_abstract(indice) == "análise cognitiva é análise"

    def test_indice_vazio_vira_string_vazia(self):
        assert _reconstruir_abstract({}) == ""
        assert _reconstruir_abstract(None) == ""

    def test_normaliza_espacos(self):
        indice = {"a": [0], "b": [1]}
        assert _reconstruir_abstract(indice) == "a b"


class TestAbstractPorDoi:
    def test_reconstroi_abstract_de_doi_valido(self):
        payload = {
            "abstract_inverted_index": {
                "Este": [0],
                "estudo": [1],
                "investiga": [2],
                "cognição.": [3],
            }
        }
        with patch(
            "apps.acervo.services.openalex.urllib.request.urlopen",
            return_value=_resposta_fake(payload),
        ):
            assert abstract_por_doi("10.1/x") == "Este estudo investiga cognição."

    def test_sem_abstract_index_retorna_vazio(self):
        with patch(
            "apps.acervo.services.openalex.urllib.request.urlopen",
            return_value=_resposta_fake({"id": "W1", "abstract_inverted_index": None}),
        ):
            assert abstract_por_doi("10.1/y") == ""

    def test_doi_invalido_nao_faz_request(self):
        with patch("apps.acervo.services.openalex.urllib.request.urlopen") as m:
            assert abstract_por_doi("nao-e-doi") == ""
            m.assert_not_called()

    def test_404_vira_vazio(self):
        erro = urllib.error.HTTPError(url="x", code=404, msg="NF", hdrs=None, fp=None)
        with patch(
            "apps.acervo.services.openalex.urllib.request.urlopen", side_effect=erro
        ):
            assert abstract_por_doi("10.1/z") == ""

    def test_timeout_vira_vazio(self):
        with patch(
            "apps.acervo.services.openalex.urllib.request.urlopen",
            side_effect=TimeoutError("timed out"),
        ):
            assert abstract_por_doi("10.1/t") == ""
