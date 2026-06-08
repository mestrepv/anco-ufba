"""Edição pós-carregamento: metadados da Busca e objetivo/estratégia do protocolo."""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.triagem.models import Busca, ProjetoMembro, ProtocoloTriagem

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


# ── Edição da Busca (campos do carregamento) ────────────────────────────────


def test_importador_edita_busca(client, proj_anco):
    dono = _user("dono")
    busca = Busca.objects.create(protocolo=proj_anco, criado_por=dono, outra_base="WoS")
    client.force_login(dono)
    resp = client.post(
        reverse("triagem_busca_editar", args=[proj_anco.slug, busca.pk]),
        data={
            "outra_base": "Scopus",
            "string_busca": "cognitive analysis",
            "n_identificados": "120",
        },
    )
    assert resp.status_code == 302
    busca.refresh_from_db()
    assert busca.outra_base == "Scopus"
    assert busca.string_busca == "cognitive analysis"
    assert busca.n_identificados == 120


def test_edita_busca_preserva_contagem_se_em_branco(client, proj_anco):
    dono = _user("dono2")
    busca = Busca.objects.create(
        protocolo=proj_anco, criado_por=dono, outra_base="WoS", n_identificados=99, n_lidos=50
    )
    client.force_login(dono)
    client.post(
        reverse("triagem_busca_editar", args=[proj_anco.slug, busca.pk]),
        data={"outra_base": "WoS"},  # n_identificados em branco
    )
    busca.refresh_from_db()
    assert busca.n_identificados == 99  # mantido
    assert busca.n_lidos == 50  # contador derivado intocado


def test_curador_edita_busca_de_outro(client, proj_anco):
    dono = _user("dono3")
    cur = _user("cur3", papel=User.Papel.CURADOR, is_staff=True)
    busca = Busca.objects.create(protocolo=proj_anco, criado_por=dono, outra_base="WoS")
    client.force_login(cur)
    resp = client.post(
        reverse("triagem_busca_editar", args=[proj_anco.slug, busca.pk]),
        data={"outra_base": "WoS", "filtros": "acesso aberto"},
    )
    assert resp.status_code == 302
    busca.refresh_from_db()
    assert busca.filtros == "acesso aberto"


def test_nao_dono_nao_edita_busca(client, proj_anco):
    dono = _user("dono4")
    intruso = _user("intruso4")
    busca = Busca.objects.create(protocolo=proj_anco, criado_por=dono, outra_base="WoS")
    client.force_login(intruso)
    resp = client.post(
        reverse("triagem_busca_editar", args=[proj_anco.slug, busca.pk]),
        data={"outra_base": "Hackeada"},
    )
    assert resp.status_code == 403
    busca.refresh_from_db()
    assert busca.outra_base == "WoS"  # intocado


# ── Edição da estratégia/objetivo do protocolo ──────────────────────────────


def test_curador_edita_estrategia(client, proj_anco):
    cur = _user("curp", papel=User.Papel.CURADOR, is_staff=True)
    client.force_login(cur)
    resp = client.post(
        reverse("triagem_protocolo", args=[proj_anco.slug]),
        data={
            "acao": "salvar_criterios",
            "pergunta_pesquisa": "Mapear a AnCo",
            "estrategia_busca": "cognitive analysis nas bases WoS/Scopus",
            "criterios_inclusao": "usa o termo",
            "criterios_exclusao": "fora de escopo",
            "termos_realce": "cognitive analysis, análise cognitiva",
        },
    )
    assert resp.status_code == 302
    proj_anco.refresh_from_db()
    assert proj_anco.estrategia_busca == "cognitive analysis nas bases WoS/Scopus"
    assert proj_anco.pergunta_pesquisa == "Mapear a AnCo"
    assert proj_anco.termos_realce == "cognitive analysis, análise cognitiva"


def test_analista_nao_edita_estrategia(client, proj_anco):
    ana = _user("anap")
    client.force_login(ana)
    resp = client.post(
        reverse("triagem_protocolo", args=[proj_anco.slug]),
        data={"acao": "salvar_criterios", "estrategia_busca": "hack"},
    )
    assert resp.status_code == 403
    proj_anco.refresh_from_db()
    assert proj_anco.estrategia_busca != "hack"


def test_rigoroso_travado_bloqueia_edicao_criterios(client, db):
    rig = ProtocoloTriagem.objects.create(nome="Rig estrategia")
    cur = User.objects.create_user(
        username="curr", email="curr@u.edu", password="x", papel=User.Papel.CURADOR, is_staff=True
    )
    ProjetoMembro.objects.get_or_create(
        projeto=rig, usuario=cur, defaults={"papel": ProjetoMembro.Papel.CURADOR}
    )
    rig.travar(cur)  # versão a priori travada
    client.force_login(cur)
    resp = client.post(
        reverse("triagem_protocolo", args=[rig.slug]),
        data={"acao": "salvar_criterios", "estrategia_busca": "nova"},
    )
    assert resp.status_code == 302
    rig.refresh_from_db()
    assert rig.estrategia_busca != "nova"  # travado: não altera
