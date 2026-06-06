"""Fase 13 — views da Revisão ANCO (atribuição, painel por modo, sorteio)."""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.triagem.models import (
    AtribuicaoAnalise,
    Busca,
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


def _analista(nome, papel=User.Papel.ANALISTA, **kw):
    return membro(
        User.objects.create_user(
            username=nome, email=f"{nome}@u.edu", password="x", papel=papel, **kw
        ),
        papel="curador" if papel == User.Papel.CURADOR else "analista",
    )


def _incluido(proj, doi):
    reg = RegistroTriagem.objects.create(
        protocolo=proj,
        titulo=f"Inc {doi}",
        doi=doi,
        ano=2021,
        status=RegistroTriagem.Status.INCLUIDO,
    )
    return promover_para_acervo(reg)


def test_a_analisar_mostra_so_atribuidos(client, proj_anco):
    ana = _analista("ana")
    meu = _incluido(proj_anco, "10/meu")
    _incluido(proj_anco, "10/outro")  # incluído, mas não atribuído a mim
    sorteio = SorteioAnalise.objects.create(projeto=proj_anco, criado_por=ana)
    AtribuicaoAnalise.objects.create(sorteio=sorteio, analista=ana, artigo=meu)

    client.force_login(ana)
    resp = client.get(reverse("triagem_a_analisar"))
    assert resp.status_code == 200
    assert resp.context["por_atribuicao"] is True
    artigos = list(resp.context["pagina"].object_list)
    assert artigos == [meu]  # só o atribuído


def test_a_analisar_sem_atribuicao_mostra_pool(client, proj_anco):
    ana = _analista("ana2")
    _incluido(proj_anco, "10/a")
    _incluido(proj_anco, "10/b")
    client.force_login(ana)
    resp = client.get(reverse("triagem_a_analisar"))
    assert resp.context["por_atribuicao"] is False
    assert len(resp.context["pagina"].object_list) == 2


def test_painel_anco_mostra_acoes_anco(client, proj_anco):
    ana = _analista("ana3")
    client.force_login(ana)
    resp = client.get(reverse("triagem_painel", args=[proj_anco.slug]))
    corpo = resp.content.decode()
    assert "Revisão ANCO" in corpo
    assert "Triar minha base" in corpo
    assert "Iniciar triagem" not in corpo  # ação do modo rigoroso, oculta


def test_sorteio_view_cria_sorteio(client, proj_anco):
    cur = _analista("cur", papel=User.Papel.CURADOR, is_staff=True)
    _analista("ana_s")  # precisa de ao menos um analista para distribuir
    _incluido(proj_anco, "10/x")
    client.force_login(cur)
    resp = client.post(
        reverse("triagem_sorteio_analise", args=[proj_anco.slug]),
        data={"modo_revisao": "unica", "cota": "5"},
    )
    assert resp.status_code == 302
    assert SorteioAnalise.objects.filter(projeto=proj_anco).exists()


def _incluido_de(proj, dono, doi):
    reg = RegistroTriagem.objects.create(
        protocolo=proj,
        titulo=f"Inc {doi}",
        doi=doi,
        ano=2021,
        status=RegistroTriagem.Status.INCLUIDO,
    )
    busca = Busca.objects.create(protocolo=proj, criado_por=dono)
    reg.origem_buscas.add(busca)
    promover_para_acervo(reg)
    return reg


def test_excluir_incluido_view(client, proj_anco):
    cur = _analista("curx", papel=User.Papel.CURADOR, is_staff=True)
    reg = _incluido_de(proj_anco, cur, "10/exc")
    client.force_login(cur)
    resp = client.post(
        reverse("triagem_incluido_excluir", args=[proj_anco.slug]),
        data={"registro_id": reg.pk, "motivo": "fora de escopo"},
    )
    assert resp.status_code == 302
    reg.refresh_from_db()
    assert reg.status == RegistroTriagem.Status.EXCLUIDO
    assert reg.artigo_id is None


def test_excluir_incluido_gate_nao_dono(client, proj_anco):
    dono = _analista("dono")
    intruso = _analista("intruso")
    reg = _incluido_de(proj_anco, dono, "10/exc2")
    client.force_login(intruso)
    resp = client.post(
        reverse("triagem_incluido_excluir", args=[proj_anco.slug]),
        data={"registro_id": reg.pk},
    )
    assert resp.status_code == 403
    reg.refresh_from_db()
    assert reg.status == RegistroTriagem.Status.INCLUIDO  # intocado


def test_autotriar_navega_sem_decidir(client, proj_anco):
    cur = _analista("curn", papel=User.Papel.CURADOR, is_staff=True)
    RegistroTriagem.objects.create(
        protocolo=proj_anco,
        titulo="A",
        doi="10/a1",
        status=RegistroTriagem.Status.IDENTIFICADO,
    )
    RegistroTriagem.objects.create(
        protocolo=proj_anco,
        titulo="B",
        doi="10/b1",
        status=RegistroTriagem.Status.IDENTIFICADO,
    )
    client.force_login(cur)
    base = reverse("triagem_autotriar", args=[proj_anco.slug])
    # curador vê todas as bases no escopo de curadoria.
    r0 = client.get(base + "?escopo=todas&lista=pendentes&i=0")
    r1 = client.get(base + "?escopo=todas&lista=pendentes&i=1")
    assert r0.context["total"] == 2 and r0.context["registro"].pk != r1.context["registro"].pk
    # navegar não decidiu nada
    assert proj_anco.registros.filter(status=RegistroTriagem.Status.IDENTIFICADO).count() == 2


def test_autotriar_desfazer_via_post(client, proj_anco):
    cur = _analista("curd", papel=User.Papel.CURADOR, is_staff=True)
    reg = _incluido_de(proj_anco, cur, "10/undoview")
    client.force_login(cur)
    resp = client.post(
        reverse("triagem_autotriar", args=[proj_anco.slug]),
        data={"acao": "desfazer", "registro_id": reg.pk, "lista": "incluidos", "i": "0"},
    )
    assert resp.status_code == 302
    reg.refresh_from_db()
    assert reg.status == RegistroTriagem.Status.IDENTIFICADO


def test_autotriar_lista_incluidos_e_excluidos_separadas(client, proj_anco):
    cur = _analista("curl", papel=User.Papel.CURADOR, is_staff=True)
    inc = _incluido_de(proj_anco, cur, "10/dec")
    exc = RegistroTriagem.objects.create(
        protocolo=proj_anco,
        titulo="Exc",
        doi="10/decx",
        status=RegistroTriagem.Status.EXCLUIDO,
    )
    client.force_login(cur)
    base = reverse("triagem_autotriar", args=[proj_anco.slug])

    ri = client.get(base + "?escopo=todas&lista=incluidos&i=0")
    assert ri.context["lista"] == "incluidos"
    assert ri.context["total"] == 1
    assert ri.context["registro"].pk == inc.pk

    re_ = client.get(base + "?escopo=todas&lista=excluidos&i=0")
    assert re_.context["lista"] == "excluidos"
    assert re_.context["total"] == 1
    assert re_.context["registro"].pk == exc.pk


def test_autotriar_view_rejeita_modo_rigoroso(client):
    rig = ProtocoloTriagem.objects.create(nome="rig")  # default RIGOROSO
    ana = membro(
        User.objects.create_user(
            username="r", email="r@u.edu", password="x", papel=User.Papel.ANALISTA
        )
    )
    # inscreve no projeto rigoroso também
    from apps.triagem.models import ProjetoMembro

    ProjetoMembro.objects.get_or_create(projeto=rig, usuario=ana)
    client.force_login(ana)
    resp = client.get(reverse("triagem_autotriar", args=[rig.slug]))
    assert resp.status_code == 302  # redireciona para registros (não é ANCO)
