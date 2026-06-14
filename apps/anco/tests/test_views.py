"""Smoke das telas ANCO (rotas montadas via ANCO_ATIVO=True em dev/test)."""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.acervo.models import Artigo
from apps.anco.models import ItemCorpus, MembroANCO, ProjetoANCO

User = get_user_model()
pytestmark = pytest.mark.django_db


@pytest.fixture
def curador(db):
    return User.objects.create_user(
        username="cur", email="cur@u.edu", password="x", pode_anco=True
    )


@pytest.fixture
def projeto(db, curador):
    p = ProjetoANCO.objects.create(nome="Piloto ANCO", pergunta_pesquisa="Q?")
    MembroANCO.objects.create(projeto=p, usuario=curador, papel=MembroANCO.Papel.CURADOR)
    art = Artigo.objects.create(titulo="Artigo X", ano=2021)
    ItemCorpus.objects.create(projeto=p, titulo="Artigo X", identificador="doi:10.1/x", artigo=art)
    return p


@pytest.mark.parametrize(
    "nome",
    ["anco_painel", "anco_importar", "anco_corpus", "anco_sorteio", "anco_estatisticas", "anco_equipe"],
)
def test_telas_curador_200(client, projeto, curador, nome):
    client.force_login(curador)
    resp = client.get(reverse(nome, args=[projeto.slug]))
    assert resp.status_code == 200


def test_projetos_lista(client, projeto, curador):
    client.force_login(curador)
    resp = client.get(reverse("anco_projetos"))
    assert resp.status_code == 200
    assert b"Piloto ANCO" in resp.content


def test_nao_membro_bloqueado(client, projeto):
    outro = User.objects.create_user(username="z", email="z@u.edu", password="x", pode_anco=True)
    client.force_login(outro)
    assert client.get(reverse("anco_painel", args=[projeto.slug])).status_code == 403


def test_sem_pode_anco_bloqueado(client, projeto):
    # Membro do projeto, mas sem acesso ao módulo (pode_anco=False) → 403.
    membro = User.objects.create_user(
        username="m2", email="m2@u.edu", password="x", pode_anco=False
    )
    MembroANCO.objects.create(projeto=projeto, usuario=membro, papel=MembroANCO.Papel.ANALISTA)
    client.force_login(membro)
    assert client.get(reverse("anco_painel", args=[projeto.slug])).status_code == 403


def test_sorteio_post_distribui(client, projeto, curador):
    # adiciona um analista e sorteia
    ana = User.objects.create_user(username="ana", email="ana@u.edu", password="x")
    MembroANCO.objects.create(projeto=projeto, usuario=ana, papel=MembroANCO.Papel.ANALISTA)
    client.force_login(curador)
    resp = client.post(reverse("anco_sorteio", args=[projeto.slug]), {"cota": 5, "modo_revisao": "unica"})
    assert resp.status_code == 302
    from apps.anco.models import AtribuicaoANCO

    assert AtribuicaoANCO.objects.filter(sorteio__projeto=projeto).count() == 1
