"""Fase 9.4 — UI: iniciar triagem, minhas-triagens, triar (mascarado), desempate."""

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.triagem.models import (
    Busca,
    DecisaoTriagem,
    ProtocoloTriagem,
    RegistroTriagem,
)
from apps.triagem.sorteio import executar_sorteio

from .conftest import membro, turl

User = get_user_model()
pytestmark = pytest.mark.django_db


def _revisor(n):
    return membro(
        User.objects.create_user(
            username=f"rev{n}",
            email=f"rev{n}@u.edu",
            password="x",
            papel=User.Papel.ANALISTA,
            revisor_aprovado=True,
            aceita_revisoes=True,
        )
    )


@pytest.fixture
def protocolo(db):
    return ProtocoloTriagem.ativo()


@pytest.fixture
def revisores(db):
    return [_revisor(i) for i in range(3)]


@pytest.fixture
def curador(db):
    return membro(
        User.objects.create_user(
            username="cur", email="cur@u.edu", password="x", papel=User.Papel.CURADOR
        ),
        papel="curador",
    )


@pytest.fixture
def leitor(db):
    return User.objects.create_user(
        username="leit", email="leit@u.edu", password="x", papel=User.Papel.LEITOR
    )


# ---- iniciar triagem -------------------------------------------------------


def test_iniciar_triagem_atribui_todos_membros(client, protocolo, revisores, curador):
    """PRISMA-ScR: iniciar atribui o registro a todos os membros, sem sorteio."""
    RegistroTriagem.objects.create(protocolo=protocolo, titulo="A", doi="10.1/a")
    client.force_login(curador)
    resp = client.post(turl("triagem_iniciar"))
    assert resp.status_code == 302
    reg = RegistroTriagem.objects.get(doi="10.1/a")
    assert reg.status == RegistroTriagem.Status.EM_TRIAGEM
    # Todos os membros (3 revisores + 1 curador) viram revisores do registro.
    assert DecisaoTriagem.objects.filter(registro=reg).count() == protocolo.membros.count()


def test_iniciar_exige_curador(client, protocolo, revisores):
    client.force_login(revisores[0])  # analista comum
    assert client.get(turl("triagem_iniciar")).status_code == 403
    assert client.post(turl("triagem_iniciar")).status_code == 403


def test_iniciar_ignora_ja_no_acervo(client, protocolo, revisores, curador):
    RegistroTriagem.objects.create(protocolo=protocolo, titulo="B", doi="10.1/b", ja_no_acervo=True)
    client.force_login(curador)
    client.post(turl("triagem_iniciar"))
    reg = RegistroTriagem.objects.get(doi="10.1/b")
    assert reg.status == RegistroTriagem.Status.IDENTIFICADO
    assert DecisaoTriagem.objects.filter(registro=reg).count() == 0


def test_iniciar_so_revisores_independentes(client, protocolo, revisores, curador):
    """O curador define quantos revisores: só os marcados recebem a triagem."""
    from apps.triagem.models import ProjetoMembro

    # Tira 2 dos 3 analistas da triagem → ficam 1 analista + o curador = 2 revisores.
    ProjetoMembro.objects.filter(
        projeto=protocolo, usuario__in=[revisores[1], revisores[2]]
    ).update(revisor_independente=False)
    RegistroTriagem.objects.create(protocolo=protocolo, titulo="A", doi="10.1/a")
    client.force_login(curador)
    client.post(turl("triagem_iniciar"))
    reg = RegistroTriagem.objects.get(doi="10.1/a")
    assert protocolo.membros.filter(revisor_independente=True).count() == 2
    assert DecisaoTriagem.objects.filter(registro=reg).count() == 2


def test_iniciar_sem_revisor_bloqueia(client, protocolo, revisores, curador):
    from apps.triagem.models import ProjetoMembro

    ProjetoMembro.objects.filter(projeto=protocolo).update(revisor_independente=False)
    RegistroTriagem.objects.create(protocolo=protocolo, titulo="A", doi="10.1/a")
    client.force_login(curador)
    resp = client.post(turl("triagem_iniciar"))
    assert resp.status_code == 302  # redireciona à equipe com aviso
    reg = RegistroTriagem.objects.get(doi="10.1/a")
    assert DecisaoTriagem.objects.filter(registro=reg).count() == 0


def test_equipe_toggle_revisor(client, protocolo, revisores, curador):
    from apps.triagem.models import ProjetoMembro

    m = ProjetoMembro.objects.get(projeto=protocolo, usuario=revisores[0])
    assert m.revisor_independente is True  # default
    client.force_login(curador)
    client.post(turl("triagem_equipe"), {"acao": "revisor", "membro_id": m.pk})
    m.refresh_from_db()
    assert m.revisor_independente is False


# ---- triar (mascarado) -----------------------------------------------------


def test_triar_mascara_coletor_e_outros(client, protocolo, revisores):
    coletor = User.objects.create_user(
        username="col",
        email="coletor@secreto.edu",
        password="x",
        papel=User.Papel.ANALISTA,
        revisor_aprovado=True,
    )
    b = Busca.objects.create(protocolo=protocolo, criado_por=coletor)
    reg = RegistroTriagem.objects.create(protocolo=protocolo, titulo="Sigiloso", doi="10.1/c")
    reg.origem_buscas.add(b)
    executar_sorteio(reg)
    decisao = DecisaoTriagem.objects.filter(registro=reg).first()

    client.force_login(decisao.revisor)
    resp = client.get(turl("triagem_triar", args=[decisao.pk]))
    assert resp.status_code == 200
    assert b"Sigiloso" in resp.content
    # mascaramento: não expõe o coletor
    assert b"coletor@secreto.edu" not in resp.content


def test_triar_so_revisor_designado(client, protocolo, revisores):
    reg = RegistroTriagem.objects.create(protocolo=protocolo, titulo="X", doi="10.1/x")
    executar_sorteio(reg)
    decisao = DecisaoTriagem.objects.filter(registro=reg).first()
    intruso = _revisor(98)
    client.force_login(intruso)
    assert client.get(turl("triagem_triar", args=[decisao.pk])).status_code == 403


def test_triar_post_registra_decisao(client, protocolo, revisores):
    reg = RegistroTriagem.objects.create(protocolo=protocolo, titulo="Y", doi="10.1/y")
    executar_sorteio(reg)
    decisao = DecisaoTriagem.objects.filter(registro=reg).first()
    client.force_login(decisao.revisor)
    resp = client.post(
        turl("triagem_triar", args=[decisao.pk]),
        data={"decisao": "incluir", "motivo_exclusao": "", "comentario": "ok"},
    )
    assert resp.status_code == 302
    decisao.refresh_from_db()
    assert decisao.decisao == "incluir"
    assert decisao.concluido_em is not None


def test_triar_auto_avanca_para_proxima(client, protocolo):
    # pool de exatamente 2 revisores → ambos pegam todos os registros
    rev = _revisor(0)
    _revisor(1)
    r1 = RegistroTriagem.objects.create(protocolo=protocolo, titulo="A1", doi="10.4/a")
    r2 = RegistroTriagem.objects.create(protocolo=protocolo, titulo="A2", doi="10.4/b")
    executar_sorteio(r1)
    executar_sorteio(r2)
    d1 = DecisaoTriagem.objects.filter(registro=r1, revisor=rev).first()
    d2 = DecisaoTriagem.objects.filter(registro=r2, revisor=rev).first()
    assert d1 and d2  # ambos sorteados para este revisor
    client.force_login(rev)
    resp = client.post(
        turl("triagem_triar", args=[d1.pk]),
        data={"decisao": "incluir", "motivo_exclusao": "", "comentario": ""},
    )
    # auto-avança direto para a próxima pendente (não volta para a lista)
    assert resp.status_code == 302
    assert resp.headers["Location"] == turl("triagem_triar", args=[d2.pk])


def test_triar_mostra_progresso_e_realce(client, protocolo, revisores):
    protocolo.termos_realce = "cognição"
    protocolo.save()
    reg = RegistroTriagem.objects.create(
        protocolo=protocolo,
        titulo="Estudo de cognição",
        doi="10.4/c",
        resumo="A cognição humana.",
    )
    executar_sorteio(reg)
    d = DecisaoTriagem.objects.filter(registro=reg).first()
    client.force_login(d.revisor)
    resp = client.get(turl("triagem_triar", args=[d.pk]))
    assert resp.status_code == 200
    assert b"de " in resp.content  # "Triagem 1 de N"
    assert b"<mark>" in resp.content  # termo destacado


def test_triar_excluir_exige_motivo(client, protocolo, revisores):
    reg = RegistroTriagem.objects.create(protocolo=protocolo, titulo="Z", doi="10.1/z")
    executar_sorteio(reg)
    decisao = DecisaoTriagem.objects.filter(registro=reg).first()
    client.force_login(decisao.revisor)
    resp = client.post(
        turl("triagem_triar", args=[decisao.pk]),
        data={"decisao": "excluir", "motivo_exclusao": "", "comentario": ""},
    )
    assert resp.status_code == 200  # re-renderiza com erro
    decisao.refresh_from_db()
    assert decisao.concluido_em is None


# ---- desempate (curador) ---------------------------------------------------


def _divergir(reg):
    executar_sorteio(reg)
    ds = list(DecisaoTriagem.objects.filter(registro=reg))
    for d, escolha in zip(ds, ["incluir", "excluir"], strict=False):
        d.decisao = escolha
        d.concluido_em = timezone.now()
        d.save()


def test_desempate_lista_divergentes(client, protocolo, revisores, curador):
    reg = RegistroTriagem.objects.create(protocolo=protocolo, titulo="Div", doi="10.1/d")
    _divergir(reg)
    client.force_login(curador)
    resp = client.get(turl("triagem_desempate"))
    assert resp.status_code == 200
    assert b"Div" in resp.content


def test_desempatar_incluir(client, protocolo, revisores, curador):
    reg = RegistroTriagem.objects.create(protocolo=protocolo, titulo="D2", doi="10.1/d2")
    _divergir(reg)
    client.force_login(curador)
    resp = client.post(
        turl("triagem_desempatar", args=[reg.pk]),
        data={"decisao": "incluir", "motivo_exclusao": ""},
    )
    assert resp.status_code == 302
    reg.refresh_from_db()
    assert reg.status == RegistroTriagem.Status.INCLUIDO
    assert reg.decidida_por_id == curador.pk


def test_leitor_nao_desempata(client, leitor):
    client.force_login(leitor)
    assert client.get(turl("triagem_desempate")).status_code == 403
