"""Testes do servico de aprovacao e fluxo completo de revisao."""

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.acervo.aprovacao import avaliar_apos_revisao
from apps.acervo.models import Analise, Artigo, Revisao
from apps.acervo.sorteio import executar_sorteio
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
        papel=User.Papel.ANALISTA,
    )


@pytest.fixture
def analista_pool(db):
    return [
        User.objects.create_user(
            username=f"a{i}",
            email=f"a{i}@u.edu.br",
            password="x",
            papel=User.Papel.ANALISTA,
        )
        for i in range(6)
    ]


@pytest.fixture
def artigo(db, vocab):
    return Artigo.objects.create(
        doi="10.x/teste",
        titulo="x",
        ano=2020,
        base_consulta=vocab,
        link_acesso="https://example.org/t",
    )


@pytest.fixture
def analise_em_revisao(db, artigo, autor, analista_pool):
    a = Analise.objects.create(
        artigo=artigo,
        analista=autor,
        status=Analise.Status.SUBMETIDA,
    )
    executar_sorteio(a)
    a.refresh_from_db()
    return a


def _concluir_revisao(rev: Revisao, parecer: str) -> None:
    rev.parecer = parecer
    rev.concluido_em = timezone.now()
    rev.save()


# ----------------------------------------------------------------------
# Cenarios obrigatorios da CLAUDE.md §9.2
# ----------------------------------------------------------------------


class TestAprovacaoSemResenha:
    def test_dois_aprovar_publica(self, analise_em_revisao):
        revs = list(Revisao.objects.filter(analise=analise_em_revisao))
        assert len(revs) == 2

        # primeira aprovacao — ainda em revisao
        _concluir_revisao(revs[0], Revisao.Parecer.APROVAR)
        # signal disparou avaliacao mas falta parecer
        analise_em_revisao.refresh_from_db()
        assert analise_em_revisao.status == Analise.Status.EM_REVISAO

        # segunda aprovacao -> publicada
        _concluir_revisao(revs[1], Revisao.Parecer.APROVAR)
        analise_em_revisao.refresh_from_db()
        assert analise_em_revisao.status == Analise.Status.PUBLICADA
        assert analise_em_revisao.publicada_em is not None

    def test_um_ajustes_volta_para_rascunho(self, analise_em_revisao):
        revs = list(Revisao.objects.filter(analise=analise_em_revisao))
        _concluir_revisao(revs[0], Revisao.Parecer.AJUSTES)
        _concluir_revisao(revs[1], Revisao.Parecer.APROVAR)
        analise_em_revisao.refresh_from_db()
        assert analise_em_revisao.status == Analise.Status.RASCUNHO

    def test_um_rejeitar_volta_para_rascunho(self, analise_em_revisao):
        revs = list(Revisao.objects.filter(analise=analise_em_revisao))
        _concluir_revisao(revs[0], Revisao.Parecer.REJEITAR)
        _concluir_revisao(revs[1], Revisao.Parecer.APROVAR)
        analise_em_revisao.refresh_from_db()
        assert analise_em_revisao.status == Analise.Status.RASCUNHO


class TestAprovacaoComResenha:
    @pytest.fixture
    def analise_com_resenha(self, db, artigo, autor, analista_pool):
        a = Analise.objects.create(
            artigo=artigo,
            analista=autor,
            status=Analise.Status.SUBMETIDA,
            resenha_critica="Resenha autoral",
        )
        executar_sorteio(a)
        a.refresh_from_db()
        return a

    def test_quatro_aprovar_publica(self, analise_com_resenha):
        revs = list(Revisao.objects.filter(analise=analise_com_resenha))
        assert len(revs) == 4

        # primeiras 3 aprovacoes — ainda em revisao
        for r in revs[:3]:
            _concluir_revisao(r, Revisao.Parecer.APROVAR)
        analise_com_resenha.refresh_from_db()
        assert analise_com_resenha.status == Analise.Status.EM_REVISAO

        # quarta aprovacao -> publicada
        _concluir_revisao(revs[3], Revisao.Parecer.APROVAR)
        analise_com_resenha.refresh_from_db()
        assert analise_com_resenha.status == Analise.Status.PUBLICADA

    def test_uma_revisao_cega_pede_ajustes_volta_rascunho(self, analise_com_resenha):
        revs = list(Revisao.objects.filter(analise=analise_com_resenha))
        # 3 aprovam, a ultima pede ajustes
        for r in revs[:-1]:
            _concluir_revisao(r, Revisao.Parecer.APROVAR)
        _concluir_revisao(revs[-1], Revisao.Parecer.AJUSTES)
        analise_com_resenha.refresh_from_db()
        assert analise_com_resenha.status == Analise.Status.RASCUNHO


# ----------------------------------------------------------------------
# Servico avaliar_apos_revisao isolado
# ----------------------------------------------------------------------


class TestAvaliarServiceIsolado:
    def test_falta_pareceres_nao_decide(self, analise_em_revisao):
        # Apenas 1 das 2 conclusoes
        rev = Revisao.objects.filter(analise=analise_em_revisao).first()
        rev.parecer = Revisao.Parecer.APROVAR
        rev.concluido_em = timezone.now()
        rev.save()
        # outra ainda nao
        resultado = avaliar_apos_revisao(analise_em_revisao)
        assert resultado.decidida is False
        assert "faltam" in resultado.motivo.lower()

    def test_status_diferente_de_em_revisao_nao_avalia(self, analise_em_revisao):
        analise_em_revisao.status = Analise.Status.RASCUNHO
        analise_em_revisao.save()
        resultado = avaliar_apos_revisao(analise_em_revisao)
        assert resultado.decidida is False
        assert "nao esta em revisao" in resultado.motivo.lower()


# ----------------------------------------------------------------------
# Fluxo completo — aceite formal da Fase 4
# ----------------------------------------------------------------------


class TestFluxoCompletoComResenha:
    def test_submissao_dispara_sorteio_e_publica_apos_4_aprovacoes(
        self, db, artigo, autor, analista_pool
    ):
        analise = Analise.objects.create(
            artigo=artigo,
            analista=autor,
            status=Analise.Status.RASCUNHO,
            resenha_critica="Texto critico autoral substantivo.",
        )
        # Simula submissao do analista
        analise.status = Analise.Status.SUBMETIDA
        analise.submetida_em = timezone.now()
        analise.save()
        # Signal disparou sorteio
        analise.refresh_from_db()
        assert analise.status == Analise.Status.EM_REVISAO
        assert Revisao.objects.filter(analise=analise).count() == 4

        # Todos aprovam
        for r in Revisao.objects.filter(analise=analise):
            _concluir_revisao(r, Revisao.Parecer.APROVAR)

        analise.refresh_from_db()
        assert analise.status == Analise.Status.PUBLICADA
        assert analise.publicada_em is not None
