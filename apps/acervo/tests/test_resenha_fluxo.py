"""Fluxo da resenha crítica: edição, submissão, revisão cega e máquina de estados."""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from apps.acervo.models import Analise, Artigo, Resenha, Revisao
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
        username="autor", email="a@u.edu.br", password="x", papel=User.Papel.ANALISTA
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
        for i in range(3)
    ]


@pytest.fixture
def analise(db, vocab, autor):
    artigo = Artigo.objects.create(
        doi="10.x/t",
        titulo="T",
        ano=2020,
        base_consulta=vocab,
        link_acesso="https://e.org/t",
    )
    return Analise.objects.create(artigo=artigo, analista=autor, status=Analise.Status.PUBLICADA)


def test_editar_resenha_cria_e_salva(client, autor, analise):
    client.force_login(autor)
    url = reverse("editar_resenha", args=[analise.pk])
    resp = client.post(url, data={"texto": "Minha resenha crítica."})
    assert resp.status_code == 302
    resenha = Resenha.objects.get(analise=analise)
    assert resenha.texto == "Minha resenha crítica."
    assert resenha.status == Resenha.Status.RASCUNHO


def test_submeter_resenha_dispara_sorteio(client, autor, analise, revisores):
    client.force_login(autor)
    Resenha.objects.create(analise=analise, texto="R", status=Resenha.Status.RASCUNHO)
    resp = client.post(reverse("submeter_resenha", args=[analise.pk]))
    assert resp.status_code == 302
    resenha = Resenha.objects.get(analise=analise)
    # signal (sync) sorteou e moveu para em_revisao
    assert resenha.status == Resenha.Status.EM_REVISAO
    assert Revisao.objects.filter(resenha=resenha).count() == 2


def test_revisao_cega_completa_marca_revisada(client, autor, analise, revisores):
    """Concluir todas as cegas com 'aprovar' leva a resenha a REVISADA (signal)."""
    resenha = Resenha.objects.create(analise=analise, texto="R", status=Resenha.Status.SUBMETIDA)
    from apps.acervo.sorteio import executar_sorteio

    executar_sorteio(resenha)
    revs = list(Revisao.objects.filter(resenha=resenha))
    assert len(revs) == 2
    # Conclui a primeira sem todas prontas: continua em revisão.
    revs[0].parecer = Revisao.Parecer.APROVAR
    revs[0].concluido_em = timezone.now()
    revs[0].save()  # dispara signal de avaliação
    resenha.refresh_from_db()
    assert resenha.status == Resenha.Status.EM_REVISAO
    # Conclui a segunda: agora todas aprovaram -> REVISADA.
    revs[1].parecer = Revisao.Parecer.APROVAR
    revs[1].concluido_em = timezone.now()
    revs[1].save()
    resenha.refresh_from_db()
    assert resenha.status == Resenha.Status.REVISADA


def test_resubmeter_resenha_publicada_reabre_revisao(client, autor, analise, revisores):
    client.force_login(autor)
    Resenha.objects.create(analise=analise, texto="R publicada", status=Resenha.Status.PUBLICADA)
    resp = client.post(reverse("submeter_resenha", args=[analise.pk]))
    assert resp.status_code == 302
    resenha = Resenha.objects.get(analise=analise)
    assert resenha.status == Resenha.Status.EM_REVISAO
    # a análise permanece publicada o tempo todo
    analise.refresh_from_db()
    assert analise.status == Analise.Status.PUBLICADA


def test_submeter_resenha_vazia_recusa(client, autor, analise):
    client.force_login(autor)
    Resenha.objects.create(analise=analise, texto="", status=Resenha.Status.RASCUNHO)
    client.post(reverse("submeter_resenha", args=[analise.pk]), follow=True)
    resenha = Resenha.objects.get(analise=analise)
    assert resenha.status == Resenha.Status.RASCUNHO  # não submeteu
