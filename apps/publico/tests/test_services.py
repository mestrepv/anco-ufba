"""Testes dos servicos de slug e citacoes ABNT/APA."""

from datetime import UTC, datetime

import pytest

from apps.acervo.models import Analise, Artigo
from apps.publico.services import (
    doi_to_slug,
    gerar_citacao_abnt,
    gerar_citacao_apa,
    slug_to_doi,
)
from apps.vocabulario.models import TermoVocabulario, Vocabulario

# ---- DOI <-> slug ----


class TestDoiSlug:
    def test_doi_canonico_round_trip(self):
        d = "10.1234/abc.456"
        assert slug_to_doi(doi_to_slug(d)) == d

    def test_doi_multi_barra_round_trip(self):
        # DOI com 2 barras (ex.: revistas OJS) — regressão do slug_to_doi.
        d = "10.54103/2037-3597/29116"
        assert slug_to_doi(doi_to_slug(d)) == d

    def test_legacy_round_trip(self):
        d = "legacy:abcdef0123456789"
        assert slug_to_doi(doi_to_slug(d)) == d

    def test_doi_canonico_slug_format(self):
        assert doi_to_slug("10.1234/abc") == "10.1234__abc"

    def test_legacy_slug_format(self):
        assert doi_to_slug("legacy:hash") == "legacy__hash"

    def test_vazio(self):
        assert doi_to_slug("") == ""
        assert slug_to_doi("") == ""

    def test_slug_sem_separador_volta_inalterado(self):
        # Caso defensivo: slug sem '__' devolve a propria string
        assert slug_to_doi("simples") == "simples"


# ---- Citacoes ----


@pytest.fixture
def vocab(db):
    v = Vocabulario.objects.create(codigo="base", nome="Base")
    return TermoVocabulario.objects.create(vocabulario=v, nome="WoS")


@pytest.fixture
def autor(db):
    from django.contrib.auth import get_user_model

    User = get_user_model()
    return User.objects.create_user(
        username="silva",
        email="silva@u.edu.br",
        password="x",
        nome_exibicao="Maria da Silva",
    )


@pytest.fixture
def analise_publicada(db, autor, vocab):
    artigo = Artigo.objects.create(
        doi="10.1/x",
        titulo="Cognição em Redes",
        ano=2022,
        base_consulta=vocab,
        link_acesso="https://e.org/x",
    )
    a = Analise.objects.create(
        artigo=artigo,
        analista=autor,
        status=Analise.Status.PUBLICADA,
        publicada_em=datetime(2024, 5, 10, tzinfo=UTC),
    )
    return a


class TestCitacaoABNT:
    def test_formato_basico(self, analise_publicada):
        c = gerar_citacao_abnt(analise_publicada)
        # Sobrenome em maiusculas
        assert "SILVA" in c
        # Iniciais
        assert "M. da" in c or "M. Da" in c
        # Titulo da analise
        assert "Cognição em Redes" in c
        # Ano publicacao
        assert "2024" in c
        # Marca da plataforma
        assert "AnCo" in c

    def test_inclui_url_da_analise(self, analise_publicada):
        c = gerar_citacao_abnt(analise_publicada)
        assert f"/analise/{analise_publicada.pk}/" in c


class TestCitacaoAPA:
    def test_formato_basico(self, analise_publicada):
        c = gerar_citacao_apa(analise_publicada)
        # Sobrenome (sem caps)
        assert "Silva" in c
        # Ano entre parenteses
        assert "(2024)" in c
        assert "Cognição em Redes" in c

    def test_url_no_apa(self, analise_publicada):
        c = gerar_citacao_apa(analise_publicada)
        assert f"/analise/{analise_publicada.pk}/" in c


class TestAutoresMultiplos:
    def test_abnt_separa_por_ponto_virgula(self, db, vocab):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        u = User.objects.create_user(
            username="multi",
            email="m@u.edu.br",
            password="x",
            nome_exibicao="João Carlos Pereira",
        )
        artigo = Artigo.objects.create(
            doi="10.1/m",
            titulo="X",
            ano=2020,
            base_consulta=vocab,
            link_acesso="https://e.org/x",
        )
        a = Analise.objects.create(
            artigo=artigo,
            analista=u,
            status=Analise.Status.PUBLICADA,
            publicada_em=datetime(2024, 1, 1, tzinfo=UTC),
        )
        c = gerar_citacao_abnt(a)
        assert "PEREIRA" in c
        assert "J. C." in c
