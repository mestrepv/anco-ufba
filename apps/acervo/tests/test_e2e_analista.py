"""
Testes E2E do M8: cobre o fluxo completo do analista cadastrado.

Não usa Selenium — apenas o Django test client. Cada teste percorre o
roteiro completo: login → cadastro de artigo (3 caminhos: DOI / ISBN /
sem identificador) → edição da análise multipasso → submissão para
revisão → verificação de signals (sorteio de revisores).
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse

from apps.acervo.models import Analise, Artigo, Revisao
from apps.acervo.services._base import LookupResultado
from apps.acervo.services.links import LinkCheckResultado
from apps.vocabulario.models import TermoVocabulario, Vocabulario

User = get_user_model()


@pytest.fixture
def vocab_base(db):
    vocab, _ = Vocabulario.objects.get_or_create(codigo="base", defaults={"nome": "Base"})
    termo, _ = TermoVocabulario.objects.get_or_create(
        vocabulario=vocab, nome="Web of Science", defaults={"ativo": True}
    )
    return termo


@pytest.fixture
def autor(db):
    # is_staff: cadastro avulso é ação de curador/admin (política da Fase 10);
    # o e2e percorre cadastro→análise→submissão a partir desse ator.
    return User.objects.create_user(
        username="autor_e2e",
        email="autor@usp.edu.br",
        password="x",
        is_staff=True,
        papel=User.Papel.ANALISTA,
    )


@pytest.fixture
def revisores(db):
    """Cria pool suficiente de revisores ativos para o sorteio funcionar."""
    return [
        User.objects.create_user(
            username=f"rev{i}",
            email=f"rev{i}@usp.edu.br",
            password="x",
            papel=User.Papel.ANALISTA,
            aceita_revisoes=True,
        )
        for i in range(4)
    ]


@pytest.fixture
def cliente(client, autor):
    client.force_login(autor)
    return client


# ---------------------------------------------------------------------------
# Fluxo 1: DOI → preview → cadastro → edição → submissão
# ---------------------------------------------------------------------------


class TestFluxoCompletoComDoi:
    @override_settings(WAYBACK_API_ENABLED=False)
    @patch("apps.acervo.views.validar_link")
    @patch("apps.acervo.views.lookup_doi")
    def test_fluxo_completo_doi(
        self, mock_lookup, mock_validar, cliente, vocab_base, autor, revisores
    ):
        mock_lookup.return_value = LookupResultado(
            encontrado=True,
            dados={
                "doi": "10.1016/j.test.2024.01",
                "titulo": "Estudo de cognição",
                "autores": ["Ana Silva"],
                "autores_str": "Ana Silva",
                "periodico": "Cogn Sci",
                "ano": 2024,
                "resumo": "Resumo do artigo.",
                "tipo": "Artigo de periódico",
            },
        )
        mock_validar.return_value = LinkCheckResultado(
            status="ok", codigo_http=200, url_final=None
        )

        # Passo 1: lookup
        resp = cliente.get(
            reverse("lookup_identificador") + "?id=10.1016/j.test.2024.01"
        )
        assert resp.status_code == 200
        assert b"Estudo de cogni" in resp.content
        mock_lookup.assert_called_once()

        # Passo 2: cadastro com metadados do lookup
        resp = cliente.post(
            reverse("cadastrar_artigo"),
            data={
                "doi": "10.1016/j.test.2024.01",
                "tipo_publicacao": "artigo",
                "titulo": "Estudo de cognição",
                "titulo_periodico": "Cogn Sci",
                "ano": "2024",
                "volume": "",
                "numero": "",
                "pagina_inicial": "",
                "pagina_final": "",
                "area": "Ciências Humanas",
                "autores": "Ana Silva",
                "vinculacao_institucional": "",
                "palavras_chaves": "",
                "resumo": "Resumo do artigo.",
                "base_consulta": vocab_base.pk,
                "link_acesso": "https://example.org/artigo",
                "link_acesso_alternativo": "",
                "artigo_pago": "",
                "acesso_aberto": "on",
            },
        )
        assert resp.status_code == 302
        artigo = Artigo.objects.get(doi="10.1016/j.test.2024.01")
        analise = Analise.objects.get(artigo=artigo, analista=autor)
        assert analise.status == Analise.Status.RASCUNHO

        # Passo 3: editar análise — passo "presenca"
        resp = cliente.post(
            reverse("editar_analise", args=[analise.pk]) + "?passo=presenca",
            data={
                "presenca_titulo": "True",
                "presenca_resumo": "True",
                "presenca_palavras_chave": "False",
                "presenca_referencias": "False",
                "presenca_corpo": "True",
                "pertinencia": "True",
                "aspectos_relevantes": "Aborda análise cognitiva em depth.",
                "define_conceito": "False",
                "definicao_extraida": "",
            },
        )
        assert resp.status_code == 302  # redireciona para o passo seguinte

        # Termos de epistemologia/teoria (obrigatórios para submeter)
        v_epist, _ = Vocabulario.objects.get_or_create(
            codigo="epistemologia", defaults={"nome": "Epistemologia"}
        )
        v_teor, _ = Vocabulario.objects.get_or_create(
            codigo="teoria", defaults={"nome": "Teoria"}
        )
        t_epist = TermoVocabulario.objects.create(vocabulario=v_epist, nome="Empirismo")
        t_teor = TermoVocabulario.objects.create(vocabulario=v_teor, nome="Cognição")

        # Passo 4: editar — passo "estrutura" (todos os campos preenchidos)
        resp = cliente.post(
            reverse("editar_analise", args=[analise.pk]) + "?passo=estrutura",
            data={
                "objeto": "Cognição em equipes",
                "objetivo": "Investigar processos",
                "foco": "Decisão coletiva",
                "metodologia": "Estudo de caso",
                "epistemologia": [t_epist.pk],
                "teoria": [t_teor.pk],
                "referenciais": "Vygotsky, Bakhtin",
                "resultados": "Identificou padrões emergentes",
                "contexto_producao": "Pesquisa de doutorado",
                "observacoes": "—",
            },
        )
        assert resp.status_code == 302

        # Passo 5: submeter para a curadoria (sem revisão por pares da análise)
        resp = cliente.post(reverse("submeter_analise", args=[analise.pk]))
        assert resp.status_code == 302

        analise.refresh_from_db()
        # Análise aguarda aprovação de curador — não há sorteio de revisores.
        assert analise.status == Analise.Status.SUBMETIDA
        assert analise.submetida_em is not None
        assert Revisao.objects.count() == 0


# ---------------------------------------------------------------------------
# Fluxo 2: ISBN → cadastro de livro
# ---------------------------------------------------------------------------


class TestFluxoCompletoComIsbn:
    @override_settings(WAYBACK_API_ENABLED=False)
    @patch("apps.acervo.views.validar_link")
    @patch("apps.acervo.views.lookup_isbn")
    def test_fluxo_isbn_cria_livro(
        self, mock_lookup, mock_validar, cliente, vocab_base, autor
    ):
        mock_lookup.return_value = LookupResultado(
            encontrado=True,
            dados={
                "titulo": "Cognitive Systems Engineering",
                "autores": ["Erik Hollnagel"],
                "autores_str": "Erik Hollnagel",
                "editora": "Academic Press",
                "ano": 2017,
                "isbn": "9780128038031",
                "tipo": "Livro",
                "resumo": "",
            },
        )
        mock_validar.return_value = LinkCheckResultado(
            status="ok", codigo_http=200, url_final=None
        )

        # Lookup
        resp = cliente.get(reverse("lookup_identificador") + "?id=9780128038031")
        assert resp.status_code == 200
        assert b"Cognitive Systems" in resp.content

        # POST do cadastro como livro
        resp = cliente.post(
            reverse("cadastrar_artigo"),
            data={
                "isbn": "9780128038031",
                "tipo_publicacao": "livro",
                "titulo": "Cognitive Systems Engineering",
                "titulo_periodico": "Academic Press",
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
        assert artigo.doi is None
        assert Analise.objects.filter(artigo=artigo, analista=autor).exists()


# ---------------------------------------------------------------------------
# Fluxo 3: sem identificador → identificador_interno determinístico
# ---------------------------------------------------------------------------


class TestFluxoSemIdentificador:
    @override_settings(WAYBACK_API_ENABLED=False)
    @patch("apps.acervo.views.validar_link")
    def test_fluxo_sem_doi_nem_isbn_gera_identificador_interno(
        self, mock_validar, cliente, vocab_base
    ):
        mock_validar.return_value = LinkCheckResultado(
            status="ok", codigo_http=200, url_final=None
        )

        resp = cliente.post(
            reverse("cadastrar_artigo"),
            data={
                "tipo_publicacao": "tese",
                "titulo": "Tese sem DOI nem ISBN",
                "titulo_periodico": "PPGDC/UFBA",
                "ano": "2023",
                "volume": "",
                "numero": "",
                "pagina_inicial": "",
                "pagina_final": "",
                "area": "Ciências Humanas",
                "autores": "Autor X",
                "vinculacao_institucional": "",
                "palavras_chaves": "",
                "resumo": "",
                "base_consulta": vocab_base.pk,
                "link_acesso": "https://repositorio.ufba.br/x",
                "link_acesso_alternativo": "",
                "artigo_pago": "",
                "acesso_aberto": "",
            },
        )
        assert resp.status_code == 302
        artigo = Artigo.objects.get(titulo="Tese sem DOI nem ISBN")
        assert artigo.doi is None
        assert artigo.isbn is None
        assert artigo.identificador_interno.startswith("legacy:")
        assert len(artigo.identificador_interno) == len("legacy:") + 16


# ---------------------------------------------------------------------------
# Fluxo 4: telas do analista renderizam (smoke E2E)
# ---------------------------------------------------------------------------


class TestSmokeNavegacaoAnalista:
    def test_minhas_analises_renderiza(self, cliente):
        resp = cliente.get(reverse("minhas_analises"))
        assert resp.status_code == 200
        assert "Minhas an\xe1lises".encode() in resp.content

    def test_buscar_redireciona_para_cadastrar(self, cliente):
        resp = cliente.get(reverse("buscar_artigo"))
        assert resp.status_code in (301, 302)
        assert reverse("cadastrar_artigo") in resp["Location"]

    def test_cadastrar_artigo_renderiza(self, cliente):
        resp = cliente.get(reverse("cadastrar_artigo"))
        assert resp.status_code == 200
        assert "Nova an\xe1lise".encode() in resp.content
