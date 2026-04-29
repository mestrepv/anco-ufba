"""Testes da pagina /acervo/planilha/ (visao tabular completa)."""

import json
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
        username="autor",
        email="autor@u.edu.br",
        password="x",
        nome_exibicao="Maria",
    )


@pytest.fixture
def analise_publicada(db, vocab, autor):
    artigo = Artigo.objects.create(
        doi="10.1/xpto",
        titulo="Cognicao distribuida em redes",
        ano=2023,
        base_consulta=vocab,
        link_acesso="https://e.org/x",
        autores="Maria da Silva; Joao P.",
    )
    return Analise.objects.create(
        artigo=artigo,
        analista=autor,
        status=Analise.Status.PUBLICADA,
        publicada_em=datetime(2024, 5, 1, tzinfo=UTC),
    )


@pytest.fixture
def analise_rascunho(db, vocab, autor):
    artigo = Artigo.objects.create(
        doi="10.1/rascunho",
        titulo="Rascunho oculto",
        ano=2024,
        base_consulta=vocab,
        link_acesso="https://e.org/r",
    )
    return Analise.objects.create(
        artigo=artigo,
        analista=autor,
        status=Analise.Status.RASCUNHO,
    )


class TestPlanilhaAcervo:
    def test_planilha_status_200(self, client, db):
        resp = client.get(reverse("acervo_planilha"))
        assert resp.status_code == 200
        # Tabulator carregado via CDN
        assert b"tabulator" in resp.content.lower()

    def test_planilha_inclui_publicada(self, client, analise_publicada):
        resp = client.get(reverse("acervo_planilha"))
        assert resp.status_code == 200
        body = resp.content.decode()
        # json_script monta um <script id="dados-planilha" type="application/json">
        assert 'id="dados-planilha"' in body
        # Titulo e DOI precisam aparecer no JSON
        assert "Cognicao distribuida em redes" in body
        assert "10.1/xpto" in body

    def test_planilha_oculta_rascunho(self, client, analise_rascunho):
        resp = client.get(reverse("acervo_planilha"))
        body = resp.content.decode()
        assert "Rascunho oculto" not in body
        assert "10.1/rascunho" not in body

    def test_planilha_serializa_campos_esperados(self, client, analise_publicada):
        resp = client.get(reverse("acervo_planilha"))
        body = resp.content.decode()
        # Extrai o blob JSON inline e valida estrutura
        marcador = 'id="dados-planilha"'
        idx = body.index(marcador)
        bloco = body[idx : idx + 4000]
        # O conteudo do <script> esta entre o primeiro > e o </script>
        inicio = bloco.index(">") + 1
        fim = bloco.index("</script>")
        dados = json.loads(bloco[inicio:fim])
        assert isinstance(dados, list)
        linha = dados[0]
        for chave in (
            "id",
            "url",
            "ano",
            "titulo",
            "autores",
            "base",
            "doi",
            "epistemologia",
            "teoria",
            "tem_resenha",
            "acesso_aberto",
            "status",
            "publicada_em",
        ):
            assert chave in linha, f"campo ausente: {chave}"
        assert linha["ano"] == 2023
        assert linha["titulo"] == "Cognicao distribuida em redes"

    def test_planilha_oculta_doi_legacy(self, client, db, vocab, autor):
        artigo = Artigo.objects.create(
            doi="legacy:abc123",
            titulo="Item legado sem DOI real",
            ano=2010,
            base_consulta=vocab,
            link_acesso="",
            eh_legado=True,
        )
        Analise.objects.create(
            artigo=artigo,
            analista=autor,
            status=Analise.Status.LEGADO,
        )
        resp = client.get(reverse("acervo_planilha"))
        body = resp.content.decode()
        # Item aparece...
        assert "Item legado sem DOI real" in body
        # ...mas o DOI sintetico nao vaza no campo doi (so seria string vazia)
        assert "legacy:abc123" not in body

    def test_planilha_linkada_da_listagem(self, client, db):
        resp = client.get(reverse("acervo_publico"))
        assert reverse("acervo_planilha").encode() in resp.content
