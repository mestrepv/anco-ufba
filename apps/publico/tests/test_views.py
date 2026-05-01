"""Testes das views publicas (Fase 5)."""

from datetime import UTC, datetime, timedelta

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from apps.acervo.models import Analise, Artigo, Revisao
from apps.publico.services import doi_to_slug
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
        username="autor1",
        email="autor@u.edu.br",
        password="x",
        papel=User.Papel.ANALISTA,
        nome_exibicao="Maria da Silva",
    )


@pytest.fixture
def revisores(db):
    return [
        User.objects.create_user(
            username=f"r{i}",
            email=f"r{i}@u.edu.br",
            password="x",
            papel=User.Papel.ANALISTA,
            nome_exibicao=f"Revisor {i}",
        )
        for i in range(4)
    ]


@pytest.fixture
def artigo_publicado(db, vocab):
    return Artigo.objects.create(
        doi="10.1/teste",
        titulo="Cognição em redes científicas",
        ano=2022,
        base_consulta=vocab,
        link_acesso="https://example.org/x",
        autores="Maria da Silva; João Pereira",
        resumo="Resumo do artigo de teste...",
    )


@pytest.fixture
def analise_publicada(db, artigo_publicado, autor):
    return Analise.objects.create(
        artigo=artigo_publicado,
        analista=autor,
        status=Analise.Status.PUBLICADA,
        publicada_em=datetime(2024, 5, 10, tzinfo=UTC),
        objeto="Análise das redes",
        objetivo="Investigar a cognição",
        pertinencia=True,
    )


# ----------------------------------------------------------------------
# Listagem
# ----------------------------------------------------------------------


class TestListagem:
    def test_listagem_publica_acessivel_sem_login(self, client, db):
        resp = client.get(reverse("acervo_publico"))
        assert resp.status_code == 200
        assert b"Acervo p" in resp.content

    def test_listagem_mostra_apenas_publicadas_e_legado(self, client, vocab, autor):
        # Cria artigos/analises em varios status
        for i, status in enumerate(
            [
                Analise.Status.PUBLICADA,
                Analise.Status.LEGADO,
                Analise.Status.RASCUNHO,
                Analise.Status.SUBMETIDA,
            ]
        ):
            a = Artigo.objects.create(
                doi=f"10.{i}/x",
                titulo=f"Art {status}",
                ano=2020,
                base_consulta=vocab,
                link_acesso="https://e.org/x",
            )
            Analise.objects.create(artigo=a, analista=autor, status=status)

        resp = client.get(reverse("acervo_publico"))
        assert resp.status_code == 200
        assert b"Art publicada" in resp.content
        assert b"Art legado" in resp.content
        assert b"Art rascunho" not in resp.content
        assert b"Art submetida" not in resp.content

    def test_busca_textual_por_titulo(self, client, analise_publicada):
        resp = client.get(reverse("acervo_publico"), {"q": "redes"})
        assert resp.status_code == 200
        assert b"Cogni" in resp.content

    def test_busca_multipalavra_inexistente_nao_retorna_tudo(
        self, client, analise_publicada
    ):
        # Regresso: ts_rank pode retornar 1e-20 (não-zero) para não-matches
        # multi-palavra, fazendo `rank > 0` deixar passar tudo. O fix usa @@.
        resp = client.get(
            reverse("acervo_publico"), {"q": "termoxyzqueñexiste outro"}
        )
        assert resp.status_code == 200
        assert analise_publicada.artigo.titulo.encode() not in resp.content
        assert b"Nenhuma" in resp.content

    def test_busca_por_doi(self, client, analise_publicada):
        resp = client.get(reverse("acervo_publico"), {"q": "10.1/teste"})
        assert resp.status_code == 200
        assert b"Cogni" in resp.content

    def test_facet_por_ano(self, client, vocab, autor):
        for ano in [2018, 2020, 2022]:
            a = Artigo.objects.create(
                doi=f"10.{ano}/x",
                titulo=f"Art {ano}",
                ano=ano,
                base_consulta=vocab,
                link_acesso="https://e.org/x",
            )
            Analise.objects.create(
                artigo=a,
                analista=autor,
                status=Analise.Status.PUBLICADA,
                publicada_em=datetime(ano, 1, 1, tzinfo=UTC),
            )

        resp = client.get(
            reverse("acervo_publico"), {"ano_min": "2020", "ano_max": "2020"}
        )
        assert resp.status_code == 200
        assert b"Art 2020" in resp.content
        assert b"Art 2018" not in resp.content
        assert b"Art 2022" not in resp.content

        # Range que cobre 2018 e 2020 mas não 2022
        resp = client.get(
            reverse("acervo_publico"), {"ano_min": "2018", "ano_max": "2020"}
        )
        assert resp.status_code == 200
        assert b"Art 2018" in resp.content
        assert b"Art 2020" in resp.content
        assert b"Art 2022" not in resp.content

    def test_facet_resenha_critica(self, client, vocab, autor):
        a1 = Artigo.objects.create(
            doi="10.1/sem",
            titulo="Sem resenha",
            ano=2020,
            base_consulta=vocab,
            link_acesso="https://e.org/a",
        )
        Analise.objects.create(
            artigo=a1,
            analista=autor,
            status=Analise.Status.PUBLICADA,
        )
        a2 = Artigo.objects.create(
            doi="10.1/com",
            titulo="Com resenha",
            ano=2020,
            base_consulta=vocab,
            link_acesso="https://e.org/b",
        )
        Analise.objects.create(
            artigo=a2,
            analista=autor,
            status=Analise.Status.PUBLICADA,
            resenha_critica="Resenha autoral.",
        )

        resp = client.get(reverse("acervo_publico"), {"resenha": "true"})
        assert resp.status_code == 200
        assert b"Com resenha" in resp.content
        assert b"Sem resenha" not in resp.content


# ----------------------------------------------------------------------
# Pagina do Artigo
# ----------------------------------------------------------------------


class TestPaginaArtigo:
    def test_artigo_acessivel_sem_login(self, client, analise_publicada):
        slug = doi_to_slug(analise_publicada.artigo.doi)
        resp = client.get(reverse("pagina_artigo", args=[slug]))
        assert resp.status_code == 200
        assert b"Cognic" in resp.content or b"Cogni" in resp.content

    def test_aviso_de_link_quebrado(self, client, vocab, autor):
        a = Artigo.objects.create(
            doi="10.1/quebrado",
            titulo="X",
            ano=2020,
            base_consulta=vocab,
            link_acesso="https://e.org/x",
            link_status="quebrado",
            link_ultima_verificacao=timezone.now(),
        )
        Analise.objects.create(
            artigo=a,
            analista=autor,
            status=Analise.Status.PUBLICADA,
        )
        slug = doi_to_slug(a.doi)
        resp = client.get(reverse("pagina_artigo", args=[slug]))
        assert resp.status_code == 200
        assert b"quebrado" in resp.content

    def test_artigo_nao_existe_404(self, client, db):
        resp = client.get(reverse("pagina_artigo", args=["10.0__naoexiste"]))
        assert resp.status_code == 404

    def test_artigo_lista_apenas_analises_publicadas(self, client, artigo_publicado, autor, vocab):
        # publicada do autor
        Analise.objects.create(
            artigo=artigo_publicado,
            analista=autor,
            status=Analise.Status.PUBLICADA,
        )
        # rascunho de outro user — nao deve aparecer
        outro = User.objects.create_user(
            username="rascunhista",
            email="r@u.edu.br",
            password="x",
            nome_exibicao="Pedro Rascunhista",
        )
        Analise.objects.create(
            artigo=artigo_publicado,
            analista=outro,
            status=Analise.Status.RASCUNHO,
        )
        slug = doi_to_slug(artigo_publicado.doi)
        resp = client.get(reverse("pagina_artigo", args=[slug]))
        assert resp.status_code == 200
        # so o autor publicado aparece
        assert b"Maria da Silva" in resp.content
        assert b"Pedro Rascunhista" not in resp.content
        # contagem mostra apenas 1
        assert b"An\xc3\xa1lises (1)" in resp.content


# ----------------------------------------------------------------------
# Pagina da Analise
# ----------------------------------------------------------------------


class TestPaginaAnalise:
    def test_analise_publicada_renderiza(self, client, analise_publicada):
        resp = client.get(reverse("pagina_analise", args=[analise_publicada.pk]))
        assert resp.status_code == 200
        assert analise_publicada.analista.nome_exibicao.encode() in resp.content

    def test_rascunho_retorna_404(self, client, vocab, autor):
        a = Artigo.objects.create(
            doi="10.r/x",
            titulo="X",
            ano=2020,
            base_consulta=vocab,
            link_acesso="https://e.org/x",
        )
        analise = Analise.objects.create(
            artigo=a,
            analista=autor,
            status=Analise.Status.RASCUNHO,
        )
        resp = client.get(reverse("pagina_analise", args=[analise.pk]))
        assert resp.status_code == 404

    def test_revisores_cegos_aparecem_anonimos(self, client, artigo_publicado, autor, revisores):
        analise = Analise.objects.create(
            artigo=artigo_publicado,
            analista=autor,
            status=Analise.Status.PUBLICADA,
            resenha_critica="X",
        )
        # 2 estruturais + 2 cegas
        prazo = timezone.now() + timedelta(days=14)
        Revisao.objects.create(
            analise=analise,
            revisor=revisores[0],
            tipo="estrutural",
            prazo_em=prazo,
            parecer="aprovar",
            concluido_em=timezone.now(),
        )
        Revisao.objects.create(
            analise=analise,
            revisor=revisores[1],
            tipo="estrutural",
            prazo_em=prazo,
            parecer="aprovar",
            concluido_em=timezone.now(),
        )
        Revisao.objects.create(
            analise=analise,
            revisor=revisores[2],
            tipo="cega",
            prazo_em=prazo,
            parecer="aprovar",
            concluido_em=timezone.now(),
        )
        Revisao.objects.create(
            analise=analise,
            revisor=revisores[3],
            tipo="cega",
            prazo_em=prazo,
            parecer="aprovar",
            concluido_em=timezone.now(),
        )

        resp = client.get(reverse("pagina_analise", args=[analise.pk]))
        assert resp.status_code == 200
        # estruturais visiveis
        assert revisores[0].nome_exibicao.encode() in resp.content
        assert revisores[1].nome_exibicao.encode() in resp.content
        # cegos NAO visiveis
        assert revisores[2].nome_exibicao.encode() not in resp.content
        assert revisores[3].nome_exibicao.encode() not in resp.content
        assert revisores[2].username.encode() not in resp.content
        assert revisores[3].username.encode() not in resp.content
        # mas tem labels A e B
        assert b"Revisor cego A" in resp.content
        assert b"Revisor cego B" in resp.content

    def test_resenha_critica_em_destaque(self, client, artigo_publicado, autor):
        analise = Analise.objects.create(
            artigo=artigo_publicado,
            analista=autor,
            status=Analise.Status.PUBLICADA,
            resenha_critica="Texto critico autoral substantivo.",
        )
        resp = client.get(reverse("pagina_analise", args=[analise.pk]))
        assert resp.status_code == 200
        assert b"peer-reviewed" in resp.content
        assert b"Texto critico autoral substantivo." in resp.content

    def test_selo_cc_by_nc_visivel(self, client, analise_publicada):
        resp = client.get(reverse("pagina_analise", args=[analise_publicada.pk]))
        assert resp.status_code == 200
        assert b"CC-BY-NC" in resp.content
        assert b"creativecommons.org" in resp.content

    def test_citacao_abnt_e_apa_renderizam(self, client, analise_publicada):
        resp = client.get(reverse("pagina_analise", args=[analise_publicada.pk]))
        assert resp.status_code == 200
        assert b"ABNT" in resp.content
        assert b"APA" in resp.content
        assert b"SILVA" in resp.content  # ABNT
        assert b"(2024)" in resp.content  # APA

    def test_link_para_historico(self, client, analise_publicada):
        resp = client.get(reverse("pagina_analise", args=[analise_publicada.pk]))
        url_historico = reverse("historico_analise", args=[analise_publicada.pk])
        assert url_historico.encode() in resp.content


class TestHistoricoAnalise:
    def test_historico_renderiza_versoes(self, client, analise_publicada):
        # forca uma alteracao para gerar mais uma versao
        analise_publicada.objeto = "alterado"
        analise_publicada.save()
        resp = client.get(reverse("historico_analise", args=[analise_publicada.pk]))
        assert resp.status_code == 200
        # pelo menos 2 versoes
        assert resp.content.count(b"<li ") >= 2

    def test_historico_de_rascunho_404(self, client, vocab, autor):
        a = Artigo.objects.create(
            doi="10.h/x",
            titulo="x",
            ano=2020,
            base_consulta=vocab,
            link_acesso="https://e.org/x",
        )
        analise = Analise.objects.create(
            artigo=a,
            analista=autor,
            status=Analise.Status.RASCUNHO,
        )
        resp = client.get(reverse("historico_analise", args=[analise.pk]))
        assert resp.status_code == 404
