"""
Testes do servico de sorteio de revisores (Fase 4).

Cobre os cenarios criticos de CLAUDE.md secao 9.2.
"""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.acervo.models import Analise, Artigo, Revisao
from apps.acervo.sorteio import (
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
def cinco_analistas(db):
    return [
        User.objects.create_user(
            username=f"rev{i}",
            email=f"rev{i}@u.edu.br",
            password="x",
            papel=User.Papel.ANALISTA,
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
        status=Analise.Status.SUBMETIDA,
    )


# ----------------------------------------------------------------------
# Cenarios obrigatorios da CLAUDE.md §9.2
# ----------------------------------------------------------------------


class TestSorteioComRevisoresSuficientes:
    def test_sorteio_normal_cria_2_estruturais(self, analise, cinco_analistas):
        resultado = executar_sorteio(analise)
        assert resultado.estruturais_criadas == 2
        assert resultado.cegas_criadas == 0
        assert resultado.fila_de_espera is False
        assert Revisao.objects.filter(analise=analise).count() == 2
        # Status migrou para em_revisao
        analise.refresh_from_db()
        assert analise.status == Analise.Status.EM_REVISAO

    def test_prazo_estrutural_e_14_dias(self, analise, cinco_analistas):
        executar_sorteio(analise)
        for r in Revisao.objects.filter(analise=analise):
            delta = r.prazo_em - r.sorteado_em
            assert 13 <= delta.days <= 14


class TestSorteioComResenhaCritica:
    def test_com_resenha_cria_2_estruturais_e_2_cegas(self, analise, cinco_analistas):
        # Marca resenha critica (atualiza tem_resenha)
        analise.resenha_critica = "Resenha autoral substantiva."
        analise.save()
        resultado = executar_sorteio(analise)
        assert resultado.estruturais_criadas == 2
        assert resultado.cegas_criadas == 2
        assert Revisao.objects.filter(analise=analise, tipo="estrutural").count() == 2
        assert Revisao.objects.filter(analise=analise, tipo="cega").count() == 2

    def test_cegos_sao_distintos_dos_estruturais(self, analise, cinco_analistas):
        analise.resenha_critica = "X"
        analise.save()
        executar_sorteio(analise)
        estruturais = set(
            Revisao.objects.filter(analise=analise, tipo="estrutural").values_list(
                "revisor_id", flat=True
            )
        )
        cegos = set(
            Revisao.objects.filter(analise=analise, tipo="cega").values_list(
                "revisor_id", flat=True
            )
        )
        assert estruturais.isdisjoint(cegos)

    def test_prazo_cega_e_21_dias(self, analise, cinco_analistas):
        analise.resenha_critica = "X"
        analise.save()
        executar_sorteio(analise)
        for r in Revisao.objects.filter(analise=analise, tipo="cega"):
            delta = r.prazo_em - r.sorteado_em
            assert 20 <= delta.days <= 21


class TestSorteioInsuficiente:
    def test_so_um_revisor_disponivel_vai_para_fila_de_espera(self, analise, db):
        # Cria apenas 1 outro analista (alem do autor)
        User.objects.create_user(
            username="unico",
            email="u@u.edu.br",
            password="x",
            papel=User.Papel.ANALISTA,
        )
        resultado = executar_sorteio(analise)
        assert resultado.fila_de_espera is True
        assert resultado.estruturais_criadas == 0
        assert "insuficientes" in resultado.motivo.lower()
        # Nao cria revisoes parciais
        assert Revisao.objects.filter(analise=analise).count() == 0
        # Status nao migra
        analise.refresh_from_db()
        assert analise.status == Analise.Status.SUBMETIDA

    def test_estruturais_ok_mas_cegos_insuficientes(self, analise, db, vocab):
        # Cria 2 analistas alem do autor (suficiente para estruturais, nao para cegas)
        for i in range(2):
            User.objects.create_user(
                username=f"r{i}",
                email=f"r{i}@u.edu.br",
                password="x",
                papel=User.Papel.ANALISTA,
            )
        analise.resenha_critica = "X"
        analise.save()
        resultado = executar_sorteio(analise)
        # Como os 2 disponiveis viram estruturais, faltam cegos -> fila de espera
        assert resultado.fila_de_espera is True
        # Idempotencia: nao criou nada
        assert Revisao.objects.filter(analise=analise).count() == 0


class TestSorteioRespeitaExclusoes:
    def test_autor_da_analise_nao_eh_sorteado(self, analise, autor, cinco_analistas):
        executar_sorteio(analise)
        revisores = Revisao.objects.filter(analise=analise).values_list("revisor_id", flat=True)
        assert autor.pk not in revisores

    def test_analista_de_outra_analise_do_mesmo_artigo_eh_excluido(
        self, analise, artigo, cinco_analistas
    ):
        # cinco_analistas[0] tambem analisou o mesmo artigo
        Analise.objects.create(artigo=artigo, analista=cinco_analistas[0])
        executar_sorteio(analise)
        revisores = Revisao.objects.filter(analise=analise).values_list("revisor_id", flat=True)
        assert cinco_analistas[0].pk not in revisores

    def test_analista_com_aceita_revisoes_false_eh_excluido(self, analise, cinco_analistas):
        cinco_analistas[0].aceita_revisoes = False
        cinco_analistas[0].save()
        # Apos exclusao, ainda restam 4 analistas + curador (none) — suficiente
        executar_sorteio(analise)
        revisores = Revisao.objects.filter(analise=analise).values_list("revisor_id", flat=True)
        assert cinco_analistas[0].pk not in revisores

    def test_analista_no_limite_de_revisoes_eh_excluido(
        self, analise, vocab, cinco_analistas, autor
    ):
        # cinco_analistas[0] tem limite=2 e ja tem 2 revisoes pendentes
        cinco_analistas[0].limite_revisoes_simultaneas = 2
        cinco_analistas[0].save()
        # Cria 2 revisoes pendentes em outras analises
        outro_artigo = Artigo.objects.create(
            doi="10.x/outro",
            titulo="x",
            ano=2020,
            base_consulta=vocab,
            link_acesso="https://e.org/o",
        )
        outra_analise = Analise.objects.create(
            artigo=outro_artigo,
            analista=autor,
            status=Analise.Status.EM_REVISAO,
        )
        for i in range(2):
            Revisao.objects.create(
                analise=outra_analise,
                revisor=cinco_analistas[0],
                tipo=Revisao.Tipo.ESTRUTURAL if i == 0 else Revisao.Tipo.CEGA,
                prazo_em=timezone.now() + timedelta(days=14),
            )
        executar_sorteio(analise)
        revisores = Revisao.objects.filter(analise=analise).values_list("revisor_id", flat=True)
        assert cinco_analistas[0].pk not in revisores

    def test_inativo_eh_excluido(self, analise, cinco_analistas):
        cinco_analistas[0].is_active = False
        cinco_analistas[0].save()
        executar_sorteio(analise)
        revisores = Revisao.objects.filter(analise=analise).values_list("revisor_id", flat=True)
        assert cinco_analistas[0].pk not in revisores

    def test_leitor_nao_eh_sorteado(self, analise, cinco_analistas, db):
        leitor = User.objects.create_user(
            username="leitor",
            email="l@u.edu.br",
            password="x",
            papel=User.Papel.LEITOR,
        )
        executar_sorteio(analise)
        revisores = Revisao.objects.filter(analise=analise).values_list("revisor_id", flat=True)
        assert leitor.pk not in revisores


class TestIdempotencia:
    def test_executar_sorteio_duas_vezes_nao_recria(self, analise, cinco_analistas):
        executar_sorteio(analise)
        antes = Revisao.objects.filter(analise=analise).count()
        executar_sorteio(analise)
        depois = Revisao.objects.filter(analise=analise).count()
        assert antes == depois == 2


class TestReSorteioPrazo:
    def test_revisao_expirada_eh_listada(self, analise, cinco_analistas):
        executar_sorteio(analise)
        rev = Revisao.objects.filter(analise=analise).first()
        rev.prazo_em = timezone.now() - timedelta(days=1)
        rev.save()
        expiradas = list(revisoes_expiradas())
        assert rev in expiradas

    def test_revisao_concluida_nao_aparece_em_expiradas(self, analise, cinco_analistas):
        executar_sorteio(analise)
        rev = Revisao.objects.filter(analise=analise).first()
        rev.prazo_em = timezone.now() - timedelta(days=1)
        rev.concluido_em = timezone.now()
        rev.save()
        assert rev not in revisoes_expiradas()

    def test_re_sortear_substitui_o_revisor(self, analise, cinco_analistas):
        executar_sorteio(analise)
        rev = Revisao.objects.filter(analise=analise).first()
        antigo_revisor_id = rev.revisor_id
        rev.prazo_em = timezone.now() - timedelta(days=1)
        rev.save()

        nova = re_sortear_revisao_expirada(rev)
        assert nova is not None
        assert nova.revisor_id != antigo_revisor_id
        assert nova.prazo_em > timezone.now()  # prazo extendido

    def test_re_sortear_sem_substituto_devolve_none(self, analise, db):
        # Apenas 2 analistas para a analise; ambos sao sorteados
        for i in range(2):
            User.objects.create_user(
                username=f"r{i}",
                email=f"r{i}@u.edu.br",
                password="x",
                papel=User.Papel.ANALISTA,
            )
        executar_sorteio(analise)
        rev = Revisao.objects.filter(analise=analise).first()
        rev.prazo_em = timezone.now() - timedelta(days=1)
        rev.save()
        # Sem candidatos novos disponiveis -> None
        novo = re_sortear_revisao_expirada(rev)
        assert novo is None

    def test_re_sortear_revisao_concluida_eh_no_op(self, analise, cinco_analistas):
        executar_sorteio(analise)
        rev = Revisao.objects.filter(analise=analise).first()
        rev.concluido_em = timezone.now()
        rev.save()
        resultado = re_sortear_revisao_expirada(rev)
        # Devolve a revisao inalterada
        assert resultado.pk == rev.pk
