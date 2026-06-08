"""Página do corpus (incluidos): resumo, status por item e filtros."""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.acervo.models import Analise
from apps.triagem.models import (
    AtribuicaoAnalise,
    ProtocoloTriagem,
    RegistroTriagem,
    SorteioAnalise,
)
from apps.triagem.promocao import promover_para_acervo

from .conftest import membro

User = get_user_model()
pytestmark = pytest.mark.django_db


@pytest.fixture
def proj_anco(db):
    p = ProtocoloTriagem.ativo()
    p.modo = ProtocoloTriagem.Modo.ANCO
    p.save()
    return p


def _user(nome, papel=User.Papel.ANALISTA, **kw):
    return membro(
        User.objects.create_user(
            username=nome, email=f"{nome}@u.edu", password="x", papel=papel, **kw
        ),
        papel="curador" if papel == User.Papel.CURADOR else "analista",
    )


def _incluido(proj, doi, ano=2020, tipo="Artigo"):
    reg = RegistroTriagem.objects.create(
        protocolo=proj,
        titulo=f"Art {doi}",
        doi=doi,
        ano=ano,
        tipo=tipo,
        status=RegistroTriagem.Status.INCLUIDO,
    )
    return reg, promover_para_acervo(reg)


def test_resumo_e_status_por_item(client, proj_anco):
    ana = _user("ana")
    _, art_sem = _incluido(proj_anco, "10/sem", ano=2010)
    _, art_an = _incluido(proj_anco, "10/an", ano=2020, tipo="Tese/Dissertação")
    _, art_atrib = _incluido(proj_anco, "10/atr", ano=2015)
    Analise.objects.create(artigo=art_an, analista=ana, status=Analise.Status.PUBLICADA)
    sorteio = SorteioAnalise.objects.create(projeto=proj_anco, criado_por=ana)
    AtribuicaoAnalise.objects.create(sorteio=sorteio, analista=ana, artigo=art_atrib)

    client.force_login(ana)
    resp = client.get(reverse("triagem_incluidos", args=[proj_anco.slug]))
    assert resp.status_code == 200
    assert resp.context["total"] == 3
    assert resp.context["n_analisado"] == 1
    assert resp.context["n_pendente"] == 1  # atribuído sem análise enviada
    assert resp.context["n_sem"] == 1
    assert resp.context["n_teses"] == 1
    assert resp.context["ano_min"] == 2010 and resp.context["ano_max"] == 2020
    corpo = resp.content.decode()
    assert "analisado" in corpo and "sem análise" in corpo and "atribuído" in corpo


def test_filtro_status_sem_analise(client, proj_anco):
    ana = _user("ana2")
    _, art_an = _incluido(proj_anco, "10/a")
    _incluido(proj_anco, "10/b")
    _incluido(proj_anco, "10/c")
    Analise.objects.create(artigo=art_an, analista=ana, status=Analise.Status.PUBLICADA)
    client.force_login(ana)
    resp = client.get(reverse("triagem_incluidos", args=[proj_anco.slug]), {"status": "sem"})
    assert resp.status_code == 200
    assert resp.context["n_filtrado"] == 2  # os 2 sem análise
    assert resp.context["tem_filtro"] is True


def test_busca_por_titulo(client, proj_anco):
    ana = _user("ana3")
    reg, _ = _incluido(proj_anco, "10/x")
    reg.titulo = "Cognitive analysis of memory"
    reg.save(update_fields=["titulo"])
    _incluido(proj_anco, "10/y")
    client.force_login(ana)
    resp = client.get(reverse("triagem_incluidos", args=[proj_anco.slug]), {"q": "memory"})
    assert resp.context["n_filtrado"] == 1
