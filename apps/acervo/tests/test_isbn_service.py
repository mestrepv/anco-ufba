"""Testes do serviço de lookup ISBN via OpenLibrary."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from django.core.cache import cache
from django.test import override_settings

from apps.acervo.services.isbn import (
    CACHE_PREFIXO,
    lookup_isbn,
    validar_isbn,
)

# Settings dev usam DummyCache; tests forçam LocMemCache para validar cache hit.
_LOCMEM_CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "test-isbn",
    }
}


@pytest.fixture(autouse=True)
def _limpa_cache_entre_testes():
    cache.clear()
    yield
    cache.clear()


def _resposta_fake(payload: dict):
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
# validar_isbn
# ---------------------------------------------------------------------------


class TestValidarIsbn:
    def test_isbn10_valido(self):
        # ISBN-10 famoso: "Quantum Computation and Quantum Information"
        assert validar_isbn("0521635039") == "0521635039"

    def test_isbn10_com_x_final(self):
        # ISBN-10 onde o checksum dá 10 → letra X
        assert validar_isbn("097522980X") == "097522980X"

    def test_isbn13_valido(self):
        # 9780128038031 — Cognitive Systems Engineering
        assert validar_isbn("9780128038031") == "9780128038031"

    def test_isbn_com_hifens(self):
        assert validar_isbn("978-0-12-803803-1") == "9780128038031"

    def test_isbn_com_espacos_e_prefixo(self):
        assert validar_isbn("  ISBN 978 0 12 803803 1  ") == "9780128038031"

    def test_checksum_invalido_isbn10(self):
        assert validar_isbn("0521635030") is None  # ultimo digito errado

    def test_checksum_invalido_isbn13(self):
        assert validar_isbn("9780128038032") is None  # ultimo digito errado

    def test_tamanho_errado(self):
        assert validar_isbn("123") is None
        assert validar_isbn("12345678901234567") is None

    def test_vazio(self):
        assert validar_isbn("") is None
        assert validar_isbn(None) is None


# ---------------------------------------------------------------------------
# lookup_isbn
# ---------------------------------------------------------------------------


class TestLookupIsbn:
    def test_isbn_valido_com_hit_retorna_dados(self):
        payload = {
            "ISBN:9780128038031": {
                "title": "Cognitive Systems Engineering",
                "authors": [{"name": "Erik Hollnagel"}, {"name": "David D. Woods"}],
                "publishers": [{"name": "Academic Press"}],
                "publish_date": "2017",
                "number_of_pages": 240,
                "subjects": [
                    {"name": "Cognitive Science"},
                    {"name": "Engineering"},
                ],
                "identifiers": {
                    "isbn_10": ["0128038039"],
                    "isbn_13": ["9780128038031"],
                },
                "cover": {
                    "small": "...s.jpg",
                    "medium": "...m.jpg",
                    "large": "https://covers.openlibrary.org/b/L.jpg",
                },
                "description": "Texto descritivo do livro.",
                "url": "https://openlibrary.org/books/x",
            }
        }
        with patch(
            "apps.acervo.services.isbn.urllib.request.urlopen",
            return_value=_resposta_fake(payload),
        ):
            r = lookup_isbn("9780128038031")

        assert r.encontrado is True
        assert r.dados["titulo"] == "Cognitive Systems Engineering"
        assert r.dados["autores"] == ["Erik Hollnagel", "David D. Woods"]
        assert r.dados["autores_str"] == "Erik Hollnagel; David D. Woods"
        assert r.dados["editora"] == "Academic Press"
        assert r.dados["ano"] == 2017
        assert r.dados["paginas"] == "240"
        assert r.dados["isbn"] == "9780128038031"
        assert r.dados["isbn_13"] == "9780128038031"
        assert r.dados["isbn_10"] == "0128038039"
        assert r.dados["tipo"] == "Livro"
        assert r.dados["palavras_chave"] == ["Cognitive Science", "Engineering"]
        assert r.dados["resumo"] == "Texto descritivo do livro."
        assert r.dados["cover"].endswith("L.jpg")

    def test_publish_date_textual_extrai_ano(self):
        payload = {
            "ISBN:9780128038031": {
                "title": "X",
                "publish_date": "January 2017",
            }
        }
        with patch(
            "apps.acervo.services.isbn.urllib.request.urlopen",
            return_value=_resposta_fake(payload),
        ):
            r = lookup_isbn("9780128038031")
        assert r.dados["ano"] == 2017

    def test_isbn_sem_hit_retorna_nao_encontrado(self):
        # OpenLibrary retorna {} quando não tem o livro
        with patch(
            "apps.acervo.services.isbn.urllib.request.urlopen",
            return_value=_resposta_fake({}),
        ):
            r = lookup_isbn("9780128038031")

        assert r.encontrado is False
        assert "não encontrado" in r.erro

    def test_isbn_invalido_nao_chama_api(self):
        with patch("apps.acervo.services.isbn.urllib.request.urlopen") as mock_urlopen:
            r = lookup_isbn("123")  # tamanho errado, checksum impossivel
        assert r.encontrado is False
        assert "inválido" in r.erro
        mock_urlopen.assert_not_called()

    def test_timeout_retorna_erro_sem_cachear(self):
        with patch(
            "apps.acervo.services.isbn.urllib.request.urlopen",
            side_effect=TimeoutError("connect timed out"),
        ):
            r = lookup_isbn("9780128038031")

        assert r.encontrado is False
        assert "timeout" in r.erro.lower()
        assert cache.get(CACHE_PREFIXO + "9780128038031") is None

    @override_settings(CACHES=_LOCMEM_CACHES)
    def test_segunda_chamada_usa_cache(self):
        cache.clear()
        payload = {"ISBN:9780128038031": {"title": "X"}}
        with patch(
            "apps.acervo.services.isbn.urllib.request.urlopen",
            return_value=_resposta_fake(payload),
        ) as mock_urlopen:
            lookup_isbn("9780128038031")
            lookup_isbn("9780128038031")  # vem do cache

        assert mock_urlopen.call_count == 1
