"""Testes das views de revisão cega da resenha — incluindo mascaramento de autoria."""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from apps.acervo.models import Analise, Artigo, ComentarioRevisao, Resenha, Revisao
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
        username="ana-distinta",
        email="autor@u.edu.br",
        password="x",
        papel=User.Papel.ANALISTA,
        nome_exibicao="Maria da Análise",
    )


@pytest.fixture
def revisores(db):
    return [
        User.objects.create_user(
            username=f"r{i}",
            email=f"r{i}@u.edu.br",
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
def resenha_em_revisao(db, artigo, autor, revisores):
    analise = Analise.objects.create(
        artigo=artigo,
        analista=autor,
        status=Analise.Status.PUBLICADA,
    )
    resenha = Resenha.objects.create(
        analise=analise,
        texto="Texto crítico autoral.",
        status=Resenha.Status.SUBMETIDA,
    )
    executar_sorteio(resenha)
    resenha.refresh_from_db()
    return resenha


class TestMinhasRevisoes:
    def test_anonimo_redireciona(self, client, db):
        resp = client.get(reverse("minhas_revisoes"))
        assert resp.status_code in (301, 302)

    def test_lista_apenas_pendentes_proprias(self, client, resenha_em_revisao):
        rev = Revisao.objects.filter(resenha=resenha_em_revisao).first()
        client.force_login(rev.revisor)
        resp = client.get(reverse("minhas_revisoes"))
        assert resp.status_code == 200
        pendentes = list(resp.context["pendentes"])
        assert rev in pendentes
        assert all(r.revisor == rev.revisor for r in pendentes)


class TestAcessoRevisar:
    def test_outro_user_recebe_403(self, client, resenha_em_revisao, revisores):
        sorteados = set(
            Revisao.objects.filter(resenha=resenha_em_revisao).values_list("revisor_id", flat=True)
        )
        rev = Revisao.objects.filter(resenha=resenha_em_revisao).first()
        outsider = next(u for u in revisores if u.pk not in sorteados)
        client.force_login(outsider)
        resp = client.get(reverse("revisar", args=[rev.pk]))
        assert resp.status_code == 403

    def test_revisao_concluida_redireciona(self, client, resenha_em_revisao):
        rev = Revisao.objects.filter(resenha=resenha_em_revisao).first()
        Revisao.objects.filter(pk=rev.pk).update(
            parecer=Revisao.Parecer.APROVAR, concluido_em=timezone.now()
        )
        client.force_login(rev.revisor)
        resp = client.get(reverse("revisar", args=[rev.pk]))
        assert resp.status_code == 302


class TestMascaramentoCega:
    def test_revisao_oculta_nome_do_autor(self, client, resenha_em_revisao, autor):
        rev = Revisao.objects.filter(resenha=resenha_em_revisao).first()
        client.force_login(rev.revisor)
        resp = client.get(reverse("revisar", args=[rev.pk]))
        assert resp.status_code == 200
        assert autor.nome_exibicao.encode() not in resp.content
        assert autor.username.encode() not in resp.content
        assert b"oculta" in resp.content.lower() or b"cega" in resp.content.lower()


class TestSubmeterRevisao:
    def test_post_valido_marca_concluida_e_grava_parecer(self, client, resenha_em_revisao):
        rev = Revisao.objects.filter(resenha=resenha_em_revisao).first()
        client.force_login(rev.revisor)
        resp = client.post(
            reverse("revisar", args=[rev.pk]),
            data={
                "parecer": Revisao.Parecer.APROVAR,
                "comentario_geral": "Resenha consistente.",
                "c_texto-campo": "texto",
                "c_texto-texto": "Argumentação bem construída.",
            },
        )
        assert resp.status_code == 302
        rev.refresh_from_db()
        assert rev.parecer == Revisao.Parecer.APROVAR
        assert rev.concluido_em is not None
        assert rev.comentario_geral == "Resenha consistente."
        com = ComentarioRevisao.objects.filter(revisao=rev, campo="texto").first()
        assert com is not None
        assert com.texto == "Argumentação bem construída."
