"""Testes do M3: Artigo aceita ausência de DOI (ISBN ou identificador interno)."""

from __future__ import annotations

import pytest

from apps.acervo.models import Artigo, _gerar_identificador_interno


class TestGerarIdentificadorInterno:
    def test_mesma_entrada_mesmo_hash(self):
        a = _gerar_identificador_interno("Título X", 2024, "Periódico Y")
        b = _gerar_identificador_interno("Título X", 2024, "Periódico Y")
        assert a == b
        assert a.startswith("legacy:")
        assert len(a) == len("legacy:") + 16

    def test_entrada_diferente_hash_diferente(self):
        a = _gerar_identificador_interno("Título X", 2024, "Y")
        b = _gerar_identificador_interno("Título Z", 2024, "Y")
        assert a != b

    def test_normaliza_caixa_e_espacos(self):
        a = _gerar_identificador_interno("  Título X  ", 2024, "Y")
        b = _gerar_identificador_interno("título x", 2024, "Y")
        assert a == b


class TestArtigoSemDoi:
    @pytest.mark.django_db
    def test_artigo_com_doi_nao_gera_identificador_interno(self):
        a = Artigo.objects.create(doi="10.1016/x", titulo="t", ano=2024)
        assert a.identificador_interno is None or a.identificador_interno == ""
        assert a.identificador_canonico == "10.1016/x"

    @pytest.mark.django_db
    def test_artigo_com_isbn_nao_gera_identificador_interno(self):
        a = Artigo.objects.create(isbn="9780128038031", titulo="Livro", ano=2024)
        assert a.identificador_interno is None or a.identificador_interno == ""
        assert a.identificador_canonico == "9780128038031"

    @pytest.mark.django_db
    def test_sem_doi_nem_isbn_gera_identificador_interno(self):
        a = Artigo.objects.create(
            titulo="Artigo sem identificador externo",
            ano=2024,
            titulo_periodico="Periódico Y",
        )
        assert a.identificador_interno is not None
        assert a.identificador_interno.startswith("legacy:")
        assert a.identificador_canonico == a.identificador_interno

    @pytest.mark.django_db
    def test_idempotente_para_mesmos_metadados(self):
        """Dois artigos com mesmo título+ano+periódico chegariam no mesmo
        identificador_interno — mas a constraint UNIQUE impede o segundo
        insert. Aqui validamos a chave determinística."""
        from django.db import IntegrityError

        Artigo.objects.create(titulo="X", ano=2024, titulo_periodico="Y")
        with pytest.raises(IntegrityError):
            Artigo.objects.create(titulo="X", ano=2024, titulo_periodico="Y")

    @pytest.mark.django_db
    def test_default_tipo_publicacao_eh_artigo(self):
        a = Artigo.objects.create(doi="10.1016/x", titulo="t", ano=2024)
        assert a.tipo_publicacao == Artigo.TipoPublicacao.ARTIGO

    @pytest.mark.django_db
    def test_tipo_publicacao_aceita_choices(self):
        a = Artigo.objects.create(
            isbn="9780128038031",
            titulo="Livro acadêmico",
            ano=2024,
            tipo_publicacao=Artigo.TipoPublicacao.LIVRO,
        )
        assert a.tipo_publicacao == "livro"

    @pytest.mark.django_db
    def test_doi_nullable_aceita_multiplos_artigos_sem_doi(self):
        """PostgreSQL aceita múltiplos NULLs em coluna UNIQUE."""
        Artigo.objects.create(titulo="A", ano=2024, titulo_periodico="P1")
        Artigo.objects.create(titulo="B", ano=2024, titulo_periodico="P2")
        Artigo.objects.create(titulo="C", ano=2024, titulo_periodico="P3")
        assert Artigo.objects.filter(doi__isnull=True).count() == 3
