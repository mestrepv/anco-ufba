"""Testes dos modelos de Artigo, Analise e Revisao."""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.utils import timezone as djtz

from apps.acervo.models import Analise, Artigo, Revisao
from apps.vocabulario.models import TermoVocabulario, Vocabulario

User = get_user_model()


@pytest.fixture
def vocab_base(db):
    return Vocabulario.objects.create(codigo="base", nome="Base")


@pytest.fixture
def termo_wos(db, vocab_base):
    return TermoVocabulario.objects.create(vocabulario=vocab_base, nome="Web of Science")


@pytest.fixture
def artigo(db, termo_wos):
    return Artigo.objects.create(
        doi="10.1234/teste.001",
        titulo="Artigo de teste",
        ano=2020,
        base_consulta=termo_wos,
    )


@pytest.fixture
def analista(db):
    return User.objects.create_user(username="analista1", email="a@x.com", password="x")


@pytest.fixture
def outro_analista(db):
    return User.objects.create_user(username="analista2", email="b@x.com", password="x")


class TestArtigo:
    def test_str_retorna_titulo_e_ano(self, artigo):
        s = str(artigo)
        assert "Artigo de teste" in s
        assert "2020" in s

    def test_doi_e_unico(self, artigo, termo_wos):
        with pytest.raises(IntegrityError):
            Artigo.objects.create(
                doi=artigo.doi,
                titulo="Outro",
                ano=2020,
                base_consulta=termo_wos,
            )

    def test_tem_link_quando_link_acesso_preenchido(self, db, termo_wos):
        a = Artigo.objects.create(
            doi="10.1/x",
            titulo="X",
            ano=2020,
            base_consulta=termo_wos,
            link_acesso="https://example.org/x",
        )
        assert a.tem_link is True

    def test_tem_link_falso_quando_ambos_vazios(self, artigo):
        assert artigo.tem_link is False


class TestAnalise:
    def test_uniq_por_artigo_e_analista(self, artigo, analista):
        Analise.objects.create(artigo=artigo, analista=analista)
        with pytest.raises(IntegrityError):
            Analise.objects.create(artigo=artigo, analista=analista)

    def test_dois_analistas_no_mesmo_artigo_e_permitido(self, artigo, analista, outro_analista):
        Analise.objects.create(artigo=artigo, analista=analista)
        # nao levanta
        Analise.objects.create(artigo=artigo, analista=outro_analista)

    def test_tem_resenha_atualiza_no_save_ao_preencher(self, artigo, analista):
        a = Analise.objects.create(artigo=artigo, analista=analista)
        assert a.tem_resenha is False
        a.resenha_critica = "Texto crítico autoral substantivo."
        a.save()
        a.refresh_from_db()
        assert a.tem_resenha is True

    def test_tem_resenha_volta_falso_ao_apagar_resenha(self, artigo, analista):
        a = Analise.objects.create(artigo=artigo, analista=analista, resenha_critica="X")
        assert a.tem_resenha is True
        a.resenha_critica = ""
        a.save()
        a.refresh_from_db()
        assert a.tem_resenha is False

    def test_tem_resenha_ignora_whitespace_puro(self, artigo, analista):
        a = Analise.objects.create(artigo=artigo, analista=analista, resenha_critica="   \n  ")
        assert a.tem_resenha is False

    def test_status_default_e_rascunho(self, artigo, analista):
        a = Analise.objects.create(artigo=artigo, analista=analista)
        assert a.status == Analise.Status.RASCUNHO

    def test_history_grava_versoes(self, artigo, analista):
        a = Analise.objects.create(artigo=artigo, analista=analista)
        a.objeto = "primeiro"
        a.save()
        a.objeto = "segundo"
        a.save()
        # 3 versoes: criacao + 2 updates
        assert a.history.count() == 3


class TestRevisao:
    def test_uniq_por_revisor_e_tipo(self, artigo, analista, outro_analista):
        analise = Analise.objects.create(artigo=artigo, analista=analista)
        prazo = djtz.now() + timedelta(days=14)
        Revisao.objects.create(
            analise=analise,
            revisor=outro_analista,
            tipo=Revisao.Tipo.ESTRUTURAL,
            prazo_em=prazo,
        )
        with pytest.raises(IntegrityError):
            Revisao.objects.create(
                analise=analise,
                revisor=outro_analista,
                tipo=Revisao.Tipo.ESTRUTURAL,
                prazo_em=prazo,
            )

    def test_mesmo_revisor_pode_estrutural_e_cega(self, artigo, analista, outro_analista):
        analise = Analise.objects.create(artigo=artigo, analista=analista)
        prazo = djtz.now() + timedelta(days=14)
        Revisao.objects.create(
            analise=analise,
            revisor=outro_analista,
            tipo=Revisao.Tipo.ESTRUTURAL,
            prazo_em=prazo,
        )
        # tipo diferente — permitido
        Revisao.objects.create(
            analise=analise,
            revisor=outro_analista,
            tipo=Revisao.Tipo.CEGA,
            prazo_em=prazo,
        )


class TestUser:
    def test_eh_curador(self, db):
        u = User.objects.create_user(
            username="c", email="c@x.com", password="x", papel=User.Papel.CURADOR
        )
        assert u.eh_curador is True
        assert u.eh_analista is True  # curador implica analista

    def test_eh_analista_para_analista(self, db):
        u = User.objects.create_user(
            username="a", email="a@x.com", password="x", papel=User.Papel.ANALISTA
        )
        assert u.eh_curador is False
        assert u.eh_analista is True

    def test_leitor_nao_e_analista(self, db):
        u = User.objects.create_user(username="l", email="l@x.com", password="x")
        assert u.eh_analista is False
        assert u.eh_curador is False
