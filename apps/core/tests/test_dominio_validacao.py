"""Testes do validador de domínio institucional (allowlist)."""

import pytest

from apps.core.adapters import email_dominio_permitido


@pytest.fixture
def dominios():
    return [
        ".edu",
        ".edu.br",
        ".ac.uk",
        "ufba.br",
        "ifba.edu.br",
        "fiocruz.br",
    ]


class TestSufixosComPonto:
    def test_aceita_dominio_que_termina_com_sufixo(self, dominios):
        assert email_dominio_permitido("user@usp.edu.br", dominios) is True
        assert email_dominio_permitido("user@harvard.edu", dominios) is True
        assert email_dominio_permitido("user@ox.ac.uk", dominios) is True

    def test_aceita_subdominio_dentro_do_sufixo(self, dominios):
        assert email_dominio_permitido("user@lab.usp.edu.br", dominios) is True

    def test_aceita_dominio_exato_sem_o_ponto_inicial(self, dominios):
        # ".edu.br" tambem aceita "edu.br" puro (caso de teste)
        assert email_dominio_permitido("user@edu.br", dominios) is True

    def test_recusa_quando_nao_termina_com_sufixo(self, dominios):
        assert email_dominio_permitido("user@gmail.com", dominios) is False
        assert email_dominio_permitido("user@example.org", dominios) is False


class TestDominioExplicito:
    def test_aceita_dominio_exato(self, dominios):
        assert email_dominio_permitido("user@ufba.br", dominios) is True
        assert email_dominio_permitido("user@fiocruz.br", dominios) is True

    def test_aceita_subdominio(self, dominios):
        assert email_dominio_permitido("user@dep.ufba.br", dominios) is True
        assert email_dominio_permitido("user@aluno.ifba.edu.br", dominios) is True

    def test_recusa_dominio_que_so_contem_o_padrao_no_meio(self, dominios):
        # "ufba.br.evil.com" nao deve passar como ufba.br
        assert email_dominio_permitido("user@ufba.br.evil.com", dominios) is False


class TestEntradasInvalidas:
    def test_recusa_email_sem_arroba(self, dominios):
        assert email_dominio_permitido("usuario.sem.arroba", dominios) is False

    def test_recusa_string_vazia(self, dominios):
        assert email_dominio_permitido("", dominios) is False

    def test_recusa_none(self, dominios):
        assert email_dominio_permitido(None, dominios) is False

    def test_recusa_quando_dominio_vazio(self, dominios):
        assert email_dominio_permitido("user@", dominios) is False


class TestCaseInsensitive:
    def test_aceita_independente_de_caixa(self, dominios):
        assert email_dominio_permitido("USER@UFBA.BR", dominios) is True
        assert email_dominio_permitido("Maria.Silva@USP.EDU.BR", dominios) is True
