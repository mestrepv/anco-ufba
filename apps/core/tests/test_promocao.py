"""Testes do fluxo de promoção a analista."""

import pytest
from django.contrib.auth import get_user_model
from django.core import mail
from django.urls import reverse

from apps.core.forms import SolicitacaoCadastroForm
from apps.core.models import SolicitacaoCadastro

User = get_user_model()


@pytest.fixture
def leitor(db):
    return User.objects.create_user(
        username="leitor1",
        email="leitor@usp.edu.br",
        password="senha-teste",
        papel=User.Papel.LEITOR,
    )


@pytest.fixture
def curador(db):
    return User.objects.create_user(
        username="curador1",
        email="curador@usp.edu.br",
        password="senha-teste",
        papel=User.Papel.CURADOR,
    )


@pytest.fixture
def cliente_leitor(client, leitor):
    client.force_login(leitor)
    return client


# ----------------------------------------------------------------------
# Form
# ----------------------------------------------------------------------


class TestSolicitacaoCadastroForm:
    def test_form_invalido_sem_justificativa(self, db, leitor):
        form = SolicitacaoCadastroForm(
            data={
                "nome_exibicao": "Maria Silva",
                "vinculo_institucional": "USP",
                "justificativa": "",
            },
            usuario=leitor,
        )
        assert form.is_valid() is False
        assert "justificativa" in form.errors

    def test_form_invalido_sem_vinculo_institucional(self, db, leitor):
        form = SolicitacaoCadastroForm(
            data={
                "nome_exibicao": "Maria Silva",
                "vinculo_institucional": "",
                "justificativa": "Pesquiso cognicao na pos.",
            },
            usuario=leitor,
        )
        assert form.is_valid() is False
        assert "vinculo_institucional" in form.errors

    def test_save_atualiza_dados_do_user(self, db, leitor):
        form = SolicitacaoCadastroForm(
            data={
                "nome_exibicao": "Maria da Silva",
                "vinculo_institucional": "USP - PPGE",
                "grupo_pesquisa": "Grupo X",
                "orcid": "0000-0001-2345-6789",
                "justificativa": "Trabalho com analise cognitiva.",
            },
            usuario=leitor,
        )
        assert form.is_valid(), form.errors
        solicitacao = form.save()
        leitor.refresh_from_db()
        assert leitor.nome_exibicao == "Maria da Silva"
        assert leitor.vinculo_institucional == "USP - PPGE"
        assert leitor.grupo_pesquisa == "Grupo X"
        assert leitor.orcid == "0000-0001-2345-6789"
        assert solicitacao.usuario == leitor
        assert solicitacao.status == SolicitacaoCadastro.Status.PENDENTE


# ----------------------------------------------------------------------
# Views
# ----------------------------------------------------------------------


class TestViewsAcessoControlado:
    def test_solicitar_promocao_exige_login(self, db, client):
        url = reverse("solicitar_promocao")
        resp = client.get(url)
        assert resp.status_code in (302, 301)
        assert "/accounts/login/" in resp["Location"]

    def test_status_exige_login(self, db, client):
        url = reverse("promocao_status")
        resp = client.get(url)
        assert resp.status_code in (302, 301)


class TestSolicitarPromocaoView:
    def test_get_renderiza_form_para_leitor(self, cliente_leitor):
        resp = cliente_leitor.get(reverse("solicitar_promocao"))
        assert resp.status_code == 200
        assert b"Solicita" in resp.content  # "Solicitação"

    def test_analista_e_redirecionado_para_home(self, db, client):
        u = User.objects.create_user(
            username="ana", email="a@u.edu.br", password="x", papel=User.Papel.ANALISTA
        )
        client.force_login(u)
        resp = client.get(reverse("solicitar_promocao"))
        assert resp.status_code == 302
        assert resp["Location"].endswith("/")

    def test_post_valido_cria_solicitacao(self, cliente_leitor, leitor):
        url = reverse("solicitar_promocao")
        resp = cliente_leitor.post(
            url,
            data={
                "nome_exibicao": "Maria Silva",
                "vinculo_institucional": "USP",
                "grupo_pesquisa": "",
                "orcid": "",
                "justificativa": "Pesquiso AnCo desde 2020.",
            },
        )
        assert resp.status_code == 302
        assert SolicitacaoCadastro.objects.filter(usuario=leitor).count() == 1

    def test_solicitacao_ja_existe_redireciona_para_status(self, cliente_leitor, leitor):
        SolicitacaoCadastro.objects.create(usuario=leitor, justificativa="J")
        resp = cliente_leitor.get(reverse("solicitar_promocao"))
        assert resp.status_code == 302
        assert reverse("promocao_status") in resp["Location"]


# ----------------------------------------------------------------------
# Sinal e fluxo de aprovacao
# ----------------------------------------------------------------------


class TestSinaisDeNotificacao:
    def test_criar_solicitacao_notifica_curadores(self, db, leitor, curador):
        mail.outbox = []
        SolicitacaoCadastro.objects.create(usuario=leitor, justificativa="J")
        assert len(mail.outbox) == 1
        assert curador.email in mail.outbox[0].to
        assert "promoção" in mail.outbox[0].subject.lower()

    def test_sem_curadores_nao_falha_e_nao_envia(self, db, leitor):
        # Sem curador ativo
        mail.outbox = []
        SolicitacaoCadastro.objects.create(usuario=leitor, justificativa="J")
        assert len(mail.outbox) == 0  # nenhum email enviado

    def test_aprovacao_promove_user_para_analista(self, db, leitor, curador):
        s = SolicitacaoCadastro.objects.create(usuario=leitor, justificativa="J")
        assert leitor.papel == User.Papel.LEITOR
        s.status = SolicitacaoCadastro.Status.APROVADA
        s.revisado_por = curador
        s.save()
        leitor.refresh_from_db()
        assert leitor.papel == User.Papel.ANALISTA

    def test_aprovacao_envia_email_de_boas_vindas_ao_usuario(self, db, leitor, curador):
        s = SolicitacaoCadastro.objects.create(usuario=leitor, justificativa="J")
        mail.outbox = []
        s.status = SolicitacaoCadastro.Status.APROVADA
        s.save()
        emails_para_leitor = [m for m in mail.outbox if leitor.email in m.to]
        assert len(emails_para_leitor) == 1
        assert "aprovada" in emails_para_leitor[0].subject.lower()

    def test_curador_nao_e_rebaixado_se_aprovado(self, db, curador):
        # Edge case: curador (que tambem podia ser analista) tem solicitacao aprovada
        s = SolicitacaoCadastro.objects.create(usuario=curador, justificativa="J")
        s.status = SolicitacaoCadastro.Status.APROVADA
        s.save()
        curador.refresh_from_db()
        assert curador.papel == User.Papel.CURADOR  # nao rebaixado

    def test_rejeicao_envia_email_informativo(self, db, leitor, curador):
        s = SolicitacaoCadastro.objects.create(
            usuario=leitor, justificativa="J", motivo_rejeicao="Falta vinculo claro."
        )
        mail.outbox = []
        s.status = SolicitacaoCadastro.Status.REJEITADA
        s.save()
        # Pelo menos 1 email para o usuario
        emails_para_leitor = [m for m in mail.outbox if leitor.email in m.to]
        assert len(emails_para_leitor) == 1
        assert "Falta vinculo claro." in emails_para_leitor[0].body

    def test_status_inalterado_nao_dispara_email(self, db, leitor, curador):
        s = SolicitacaoCadastro.objects.create(usuario=leitor, justificativa="J")
        mail.outbox = []
        # Salva sem mudar status
        s.justificativa = "Outra justificativa"
        s.save()
        # Nenhum email novo (criacao ja consumiu o de notificacao)
        assert len(mail.outbox) == 0
