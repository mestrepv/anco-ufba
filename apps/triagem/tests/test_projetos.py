"""Criação de projeto: curador pode criar e escolhe o modo (ANCO / PRISMA-ScR)."""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.triagem.models import ProjetoMembro, ProtocoloTriagem

User = get_user_model()
pytestmark = pytest.mark.django_db


def _user(nome, papel=User.Papel.ANALISTA, **kw):
    return User.objects.create_user(
        username=nome, email=f"{nome}@u.edu", password="x", papel=papel, **kw
    )


def test_curador_cria_projeto(client):
    cur = _user("cur", papel=User.Papel.CURADOR)
    client.force_login(cur)
    resp = client.post(
        reverse("triagem_novo_projeto"),
        data={"nome": "Projeto PRISMA", "estrategia_busca": "cognitive analysis"},
    )
    assert resp.status_code == 302
    p = ProtocoloTriagem.objects.get(nome="Projeto PRISMA")
    assert p.estrategia_busca == "cognitive analysis"
    # criador vira curador do projeto
    assert ProjetoMembro.objects.filter(
        projeto=p, usuario=cur, papel=ProjetoMembro.Papel.CURADOR
    ).exists()


def test_analista_comum_nao_cria(client):
    ana = _user("ana", papel=User.Papel.ANALISTA)
    client.force_login(ana)
    resp = client.get(reverse("triagem_novo_projeto"))
    assert resp.status_code == 403
    resp_post = client.post(reverse("triagem_novo_projeto"), data={"nome": "Hack", "modo": "anco"})
    assert resp_post.status_code == 403
    assert not ProtocoloTriagem.objects.filter(nome="Hack").exists()


def test_curador_ve_botao_criar_na_lista(client):
    cur = _user("cur4", papel=User.Papel.CURADOR)
    client.force_login(cur)
    resp = client.get(reverse("triagem_projetos"))
    assert resp.context["pode_criar"] is True


def test_analista_nao_ve_botao_criar(client):
    ana = _user("ana2", papel=User.Papel.ANALISTA)
    client.force_login(ana)
    resp = client.get(reverse("triagem_projetos"))
    assert resp.context["pode_criar"] is False
