"""Fase 11.2/11.3 — checklist PRISMA-ScR + protocolo versionado/travado."""

import pytest
from django.contrib.auth import get_user_model

from apps.triagem import checklist as cl
from apps.triagem.models import ProtocoloTriagem, SnapshotProtocolo

from .conftest import membro, turl

User = get_user_model()
pytestmark = pytest.mark.django_db


@pytest.fixture
def analista(db):
    return membro(
        User.objects.create_user(
            username="ana", email="ana@x.org", password="x", papel=User.Papel.ANALISTA
        )
    )


@pytest.fixture
def curador(db):
    return membro(
        User.objects.create_user(
            username="cur", email="cur@x.org", password="x", papel=User.Papel.CURADOR
        ),
        papel="curador",
    )


# ── checklist ────────────────────────────────────────────────────────────


def test_checklist_tem_22_itens_com_12_e_16_opcionais():
    assert len(cl.ITENS) == 22
    opcionais = [num for _s, num, *_r, opc in cl.ITENS if opc]
    assert opcionais == [12, 16]


def test_checklist_view_renderiza(client, analista):
    client.force_login(analista)
    r = client.get(turl("triagem_checklist"))
    assert r.status_code == 200
    assert b"PRISMA-ScR" in r.content


def test_checklist_csv(client, analista):
    client.force_login(analista)
    r = client.get(turl("triagem_checklist"), {"formato": "csv"})
    assert r.status_code == 200
    assert r["Content-Type"] == "text/csv"
    linhas = r.content.decode("utf-8").strip().splitlines()
    assert len(linhas) == 23  # cabeçalho + 22 itens


# ── protocolo: lock / versão ─────────────────────────────────────────────


def test_protocolo_view_get(client, analista):
    client.force_login(analista)
    r = client.get(turl("triagem_protocolo"))
    assert r.status_code == 200


def test_analista_nao_gerencia_protocolo(client, analista):
    client.force_login(analista)
    r = client.post(turl("triagem_protocolo"), {"acao": "travar"})
    assert r.status_code == 403


def test_curador_salva_registro_e_dois_estagios(client, curador):
    client.force_login(curador)
    r = client.post(
        turl("triagem_protocolo"),
        {"acao": "salvar", "registro_externo": "https://osf.io/abc", "usa_texto_completo": "on"},
    )
    assert r.status_code == 302
    p = ProtocoloTriagem.ativo()
    assert p.registro_externo == "https://osf.io/abc"
    assert p.usa_texto_completo is True


def test_curador_trava_e_abre_nova_versao(client, curador):
    client.force_login(curador)
    p = ProtocoloTriagem.ativo()
    assert p.versao == 1 and p.travado_em is None

    client.post(turl("triagem_protocolo"), {"acao": "travar"})
    p.refresh_from_db()
    assert p.travado_em is not None
    assert SnapshotProtocolo.objects.filter(protocolo=p, versao=1).exists()

    client.post(turl("triagem_protocolo"), {"acao": "nova_versao"})
    p.refresh_from_db()
    assert p.versao == 2 and p.travado_em is None


def test_snapshot_guarda_dados_do_protocolo(curador):
    p = ProtocoloTriagem.ativo()
    p.pergunta_pesquisa = "O que é análise cognitiva?"
    p.save(update_fields=["pergunta_pesquisa"])
    p.travar(curador)
    snap = SnapshotProtocolo.objects.get(protocolo=p, versao=1)
    assert snap.dados["pergunta_pesquisa"] == "O que é análise cognitiva?"
    assert snap.travado_por == curador
