"""Testes das views de revisao (Fase 4) — incluindo mascaramento de autoria."""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from apps.acervo.models import Analise, Artigo, ComentarioRevisao, Revisao
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
def analise_em_revisao_com_resenha(db, artigo, autor, revisores):
    a = Analise.objects.create(
        artigo=artigo,
        analista=autor,
        status=Analise.Status.SUBMETIDA,
        resenha_critica="Texto critico autoral.",
        objeto="Cognição em redes",
    )
    executar_sorteio(a)
    a.refresh_from_db()
    return a


# ----------------------------------------------------------------------
# Lista "minhas revisoes"
# ----------------------------------------------------------------------


class TestMinhasRevisoes:
    def test_anonimo_redireciona(self, client, db):
        resp = client.get(reverse("minhas_revisoes"))
        assert resp.status_code in (301, 302)

    def test_lista_apenas_pendentes_proprias(self, client, analise_em_revisao_com_resenha):
        rev = Revisao.objects.filter(analise=analise_em_revisao_com_resenha).first()
        client.force_login(rev.revisor)
        resp = client.get(reverse("minhas_revisoes"))
        assert resp.status_code == 200
        pendentes = list(resp.context["pendentes"])
        assert rev in pendentes
        # nao mostra revisoes de outros
        assert all(r.revisor == rev.revisor for r in pendentes)


# ----------------------------------------------------------------------
# View revisar — acesso e mascaramento
# ----------------------------------------------------------------------


class TestAcessoRevisar:
    def test_outro_user_recebe_403(self, client, analise_em_revisao_com_resenha, revisores):
        rev = Revisao.objects.filter(analise=analise_em_revisao_com_resenha).first()
        # logue um analista que NAO foi sorteado
        outsider = next(u for u in revisores if u.pk != rev.revisor_id)
        # se outsider tambem foi sorteado por azar, pega um que nao foi
        sorteados = set(
            Revisao.objects.filter(analise=analise_em_revisao_com_resenha).values_list(
                "revisor_id", flat=True
            )
        )
        outsider = next(u for u in revisores if u.pk not in sorteados)
        client.force_login(outsider)
        resp = client.get(reverse("revisar", args=[rev.pk]))
        assert resp.status_code == 403

    def test_revisao_concluida_redireciona(self, client, analise_em_revisao_com_resenha):
        rev = Revisao.objects.filter(analise=analise_em_revisao_com_resenha).first()
        rev.parecer = Revisao.Parecer.APROVAR
        rev.concluido_em = timezone.now()
        rev.save()
        client.force_login(rev.revisor)
        resp = client.get(reverse("revisar", args=[rev.pk]))
        assert resp.status_code == 302


class TestMascaramentoCega:
    def test_revisao_estrutural_mostra_nome_do_autor(
        self, client, analise_em_revisao_com_resenha, autor
    ):
        rev = Revisao.objects.filter(
            analise=analise_em_revisao_com_resenha,
            tipo=Revisao.Tipo.ESTRUTURAL,
        ).first()
        client.force_login(rev.revisor)
        resp = client.get(reverse("revisar", args=[rev.pk]))
        assert resp.status_code == 200
        # nome do autor aparece
        assert autor.nome_exibicao.encode() in resp.content

    def test_revisao_cega_oculta_nome_do_autor(self, client, analise_em_revisao_com_resenha, autor):
        rev = Revisao.objects.filter(
            analise=analise_em_revisao_com_resenha,
            tipo=Revisao.Tipo.CEGA,
        ).first()
        client.force_login(rev.revisor)
        resp = client.get(reverse("revisar", args=[rev.pk]))
        assert resp.status_code == 200
        # nome do autor NAO aparece
        assert autor.nome_exibicao.encode() not in resp.content
        assert autor.username.encode() not in resp.content
        # mas tem indicacao de "autoria oculta"
        assert b"oculta" in resp.content.lower() or b"cega" in resp.content.lower()


# ----------------------------------------------------------------------
# Submissao da revisao
# ----------------------------------------------------------------------


class TestSubmeterRevisao:
    def test_post_valido_marca_concluida_e_grava_parecer(
        self, client, analise_em_revisao_com_resenha
    ):
        rev = Revisao.objects.filter(analise=analise_em_revisao_com_resenha).first()
        client.force_login(rev.revisor)
        resp = client.post(
            reverse("revisar", args=[rev.pk]),
            data={
                "parecer": Revisao.Parecer.APROVAR,
                "comentario_geral": "Análise consistente.",
                # comentarios ancorados em forms vazios (prefixos c_<campo>)
                "c_objeto-campo": "objeto",
                "c_objeto-texto": "Objeto bem delimitado.",
                "c_objetivo-campo": "objetivo",
                "c_objetivo-texto": "",
                "c_foco-campo": "foco",
                "c_foco-texto": "",
                "c_metodologia-campo": "metodologia",
                "c_metodologia-texto": "",
                "c_resultados-campo": "resultados",
                "c_resultados-texto": "",
                "c_aspectos_relevantes-campo": "aspectos_relevantes",
                "c_aspectos_relevantes-texto": "",
                "c_definicao_extraida-campo": "definicao_extraida",
                "c_definicao_extraida-texto": "",
                "c_resenha_critica-campo": "resenha_critica",
                "c_resenha_critica-texto": "",
            },
        )
        assert resp.status_code == 302
        rev.refresh_from_db()
        assert rev.parecer == Revisao.Parecer.APROVAR
        assert rev.concluido_em is not None
        assert rev.comentario_geral == "Análise consistente."
        # comentario ancorado foi criado
        com = ComentarioRevisao.objects.filter(revisao=rev, campo="objeto").first()
        assert com is not None
        assert com.texto == "Objeto bem delimitado."
