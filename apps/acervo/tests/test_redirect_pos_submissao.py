"""Pós-submissão de análise ANCO devolve o analista à SUA fila de sorteados
(`anco_analisar`), não à triagem PRISMA (`triagem_a_analisar`). Separação
ANCO × PRISMA — ver memória `anco-e-prisma-modulos-separados`."""

from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.acervo.models import Analise, Artigo
from apps.acervo.views import _projeto_anco_do_analista
from apps.anco.models import AtribuicaoANCO, ProjetoANCO, SorteioANCO

User = get_user_model()
pytestmark = pytest.mark.django_db


@pytest.fixture
def analista(db):
    return User.objects.create_user(
        username="a", email="a@u.edu", password="x", papel="analista", pode_anco=True
    )


@pytest.fixture
def projeto(db):
    return ProjetoANCO.objects.create(nome="Piloto", slug="piloto-x", pergunta_pesquisa="Q?")


def _atribuir(projeto, analista, artigo):
    s = SorteioANCO.objects.create(projeto=projeto)
    AtribuicaoANCO.objects.create(sorteio=s, analista=analista, artigo=artigo)
    return s


def test_helper_resolve_projeto_pela_atribuicao(projeto, analista):
    art = Artigo.objects.create(titulo="T", ano=2023)
    _atribuir(projeto, analista, art)
    assert _projeto_anco_do_analista(analista, art) == projeto
    assert _projeto_anco_do_analista(analista) == projeto


def test_helper_sem_atribuicao_retorna_none(analista):
    assert _projeto_anco_do_analista(analista) is None


def test_submeter_redireciona_para_worklist_anco(client, projeto, analista):
    art = Artigo.objects.create(titulo="T", ano=2023)
    _atribuir(projeto, analista, art)
    analise = Analise.objects.create(
        artigo=art, analista=analista, status=Analise.Status.RASCUNHO
    )
    client.force_login(analista)
    # Não é o foco testar a trava de campos; garantimos o roteamento pós-submissão.
    with patch.object(Analise, "campos_faltantes_submissao", return_value=[]):
        resp = client.post(reverse("submeter_analise", args=[analise.pk]))
    assert resp.status_code == 302
    assert resp.url == reverse("anco_analisar", args=[projeto.slug])
    assert "/triagem/" not in resp.url


def test_submeter_sem_atribuicao_cai_no_fallback(client, analista):
    art = Artigo.objects.create(titulo="T", ano=2023)
    analise = Analise.objects.create(
        artigo=art, analista=analista, status=Analise.Status.RASCUNHO
    )
    client.force_login(analista)
    with patch.object(Analise, "campos_faltantes_submissao", return_value=[]):
        resp = client.post(reverse("submeter_analise", args=[analise.pk]))
    assert resp.status_code == 302
    assert resp.url == reverse("minhas_analises")


def test_minhas_analises_linka_worklist_anco_nao_prisma(client, projeto, analista):
    art = Artigo.objects.create(titulo="T", ano=2023)
    _atribuir(projeto, analista, art)
    Analise.objects.create(artigo=art, analista=analista, status=Analise.Status.RASCUNHO)
    client.force_login(analista)
    resp = client.get(reverse("minhas_analises"))
    corpo = resp.content.decode()
    assert reverse("anco_analisar", args=[projeto.slug]) in corpo
    assert reverse("triagem_a_analisar") not in corpo
