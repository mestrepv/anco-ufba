"""
Testes do sorteio de revisores cegos para RESENHAS críticas.

A revisão por pares vale só para resenhas (a análise é publicada por curadoria).
"""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.acervo.models import Analise, Artigo, Resenha, Revisao
from apps.acervo.sorteio import (
    PRAZO_CEGA_DIAS,
    executar_sorteio,
    re_sortear_revisao_expirada,
    revisoes_expiradas,
)
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
def cinco_revisores(db):
    return [
        User.objects.create_user(
            username=f"rev{i}",
            email=f"rev{i}@u.edu.br",
            password="x",
            papel=User.Papel.ANALISTA,
            revisor_aprovado=True,
        )
        for i in range(5)
    ]


@pytest.fixture
def artigo(db, vocab):
    return Artigo.objects.create(
        doi="10.x/teste",
        titulo="Artigo teste",
        ano=2020,
        base_consulta=vocab,
        link_acesso="https://example.org/t",
    )


@pytest.fixture
def analise(db, artigo, autor):
    return Analise.objects.create(
        artigo=artigo,
        analista=autor,
        status=Analise.Status.PUBLICADA,
    )


@pytest.fixture
def resenha(db, analise):
    return Resenha.objects.create(
        analise=analise,
        texto="Resenha crítica.",
        status=Resenha.Status.SUBMETIDA,
    )


class TestSorteioComRevisoresSuficientes:
    def test_cria_2_revisores_cegos(self, resenha, cinco_revisores):
        resultado = executar_sorteio(resenha)
        assert resultado.cegas_criadas == 2
        assert resultado.fila_de_espera is False
        assert Revisao.objects.filter(resenha=resenha).count() == 2
        resenha.refresh_from_db()
        assert resenha.status == Resenha.Status.EM_REVISAO

    def test_prazo_cega_e_21_dias(self, resenha, cinco_revisores):
        executar_sorteio(resenha)
        for r in Revisao.objects.filter(resenha=resenha):
            assert (PRAZO_CEGA_DIAS - 1) <= (r.prazo_em - r.sorteado_em).days <= PRAZO_CEGA_DIAS

    def test_exclui_autor_da_analise(self, resenha, cinco_revisores, autor):
        executar_sorteio(resenha)
        sorteados = set(
            Revisao.objects.filter(resenha=resenha).values_list("revisor_id", flat=True)
        )
        assert autor.pk not in sorteados


class TestExclusoes:
    def test_exclui_coautor_do_mesmo_artigo(self, resenha, artigo, cinco_revisores):
        # Um revisor vira autor de OUTRA análise do mesmo artigo → excluído.
        coautor = cinco_revisores[0]
        Analise.objects.create(artigo=artigo, analista=coautor)
        executar_sorteio(resenha)
        sorteados = set(
            Revisao.objects.filter(resenha=resenha).values_list("revisor_id", flat=True)
        )
        assert coautor.pk not in sorteados

    def test_exclui_revisor_nao_aprovado(self, resenha, db, artigo):
        # Só revisores aprovados elegíveis; sem aprovados → fila de espera.
        User.objects.create_user(
            username="naoaprovado",
            email="n@u.edu.br",
            password="x",
            papel=User.Papel.ANALISTA,
            revisor_aprovado=False,
        )
        resultado = executar_sorteio(resenha)
        assert resultado.fila_de_espera is True
        assert Revisao.objects.filter(resenha=resenha).count() == 0


class TestRevisoresInsuficientes:
    def test_um_revisor_vai_para_fila_de_espera(self, resenha, db):
        User.objects.create_user(
            username="unico",
            email="u@u.edu.br",
            password="x",
            papel=User.Papel.ANALISTA,
            revisor_aprovado=True,
        )
        resultado = executar_sorteio(resenha)
        assert resultado.fila_de_espera is True
        assert resultado.cegas_criadas == 0
        assert Revisao.objects.filter(resenha=resenha).count() == 0
        resenha.refresh_from_db()
        assert resenha.status == Resenha.Status.SUBMETIDA


class TestIdempotencia:
    def test_nao_recria_se_ha_ciclo_pendente(self, resenha, cinco_revisores):
        executar_sorteio(resenha)
        resultado2 = executar_sorteio(resenha)
        assert resultado2.cegas_criadas == 0
        assert Revisao.objects.filter(resenha=resenha).count() == 2


class TestReSorteio:
    def test_re_sortear_revisao_expirada_troca_revisor(self, resenha, cinco_revisores):
        executar_sorteio(resenha)
        rev = Revisao.objects.filter(resenha=resenha).first()
        rev.prazo_em = timezone.now() - timedelta(days=1)
        rev.save(update_fields=["prazo_em"])
        original = rev.revisor_id
        novo = re_sortear_revisao_expirada(rev)
        assert novo is not None
        assert novo.revisor_id != original

    def test_revisoes_expiradas_lista_so_pendentes_vencidas(self, resenha, cinco_revisores):
        executar_sorteio(resenha)
        Revisao.objects.filter(resenha=resenha).update(prazo_em=timezone.now() - timedelta(days=1))
        assert revisoes_expiradas().count() == 2
