"""Navegador de fontes (registros) de uma importação: navegação + edição + sync."""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.acervo.models import Artigo
from apps.triagem.models import Busca, ProtocoloTriagem, RegistroTriagem
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


def _busca_com_fontes(proj, dono, n):
    busca = Busca.objects.create(protocolo=proj, criado_por=dono, outra_base="WoS")
    regs = []
    for k in range(n):
        r = RegistroTriagem.objects.create(
            protocolo=proj, titulo=f"Fonte {k}", doi=f"10/f{k}", identificador=f"id{k}"
        )
        r.origem_buscas.add(busca)
        regs.append(r)
    return busca, regs


def test_fonte_renderiza_ficha_com_tipo(client, proj_anco):
    """Regressão: a ficha canônica não pode quebrar quando o registro tem `tipo`
    (CharField livre, sem choices — não existe get_tipo_display)."""
    dono = _user("dono_tipo")
    busca = Busca.objects.create(protocolo=proj_anco, criado_por=dono, outra_base="WoS")
    r = RegistroTriagem.objects.create(
        protocolo=proj_anco,
        titulo="Estudo sobre cognição",
        doi="10/tipo",
        identificador="idtipo",
        tipo="Artigo",
        autores="Fulano de Tal",
        ano=2020,
        titulo_periodico="Revista Y",
    )
    r.origem_buscas.add(busca)
    client.force_login(dono)
    url = reverse("triagem_busca_fonte", args=[proj_anco.slug, busca.pk])
    resp = client.get(url + "?i=0")
    assert resp.status_code == 200
    assert b"Estudo sobre cogni" in resp.content  # título da ficha aparece
    assert b"Artigo" in resp.content  # tipo aparece (branch que quebrava)


def test_navega_fontes_com_indice(client, proj_anco):
    dono = _user("dono")
    busca, regs = _busca_com_fontes(proj_anco, dono, 3)
    client.force_login(dono)
    url = reverse("triagem_busca_fonte", args=[proj_anco.slug, busca.pk])

    r0 = client.get(url + "?i=0")
    assert r0.status_code == 200
    assert r0.context["total"] == 3 and r0.context["pos"] == 1
    assert r0.context["url_anterior"] == ""  # primeira: sem voltar
    assert r0.context["url_proximo"].endswith("?i=1")

    r1 = client.get(url + "?i=1")
    assert r1.context["registro"].pk != r0.context["registro"].pk
    assert r1.context["url_anterior"].endswith("?i=0")

    # índice fora do intervalo é fixado no limite
    rfim = client.get(url + "?i=99")
    assert rfim.context["pos"] == 3 and rfim.context["url_proximo"] == ""


def test_edita_fonte_e_sincroniza_artigo(client, proj_anco):
    dono = _user("dono2")
    busca, regs = _busca_com_fontes(proj_anco, dono, 1)
    reg = regs[0]
    reg.status = RegistroTriagem.Status.INCLUIDO
    reg.save(update_fields=["status"])
    artigo = promover_para_acervo(reg)
    client.force_login(dono)
    resp = client.post(
        reverse("triagem_busca_fonte", args=[proj_anco.slug, busca.pk]),
        data={
            "i": "0",
            "titulo": "Fonte 0",
            "autores": "Silva, J.",
            "ano": "2021",
            "titulo_periodico": "Rev X",
            "doi": "10/f0",
            "isbn": "",
            "idioma": "en",
            "tipo": "Artigo",
            "palavras_chaves": "cognição; análise",
            "resumo": "Um resumo que faltava.",
            "link": "",
        },
    )
    assert resp.status_code == 302
    reg.refresh_from_db()
    artigo.refresh_from_db()
    assert reg.resumo == "Um resumo que faltava."
    assert reg.palavras_chaves == "cognição; análise"
    # sincronizado no artigo (não-legado)
    assert artigo.resumo == "Um resumo que faltava."
    assert artigo.palavras_chaves == "cognição; análise"
    assert artigo.idioma == "en"


def test_nao_sincroniza_artigo_legado(client, proj_anco):
    dono = _user("dono3")
    busca, regs = _busca_com_fontes(proj_anco, dono, 1)
    reg = regs[0]
    legado = Artigo.objects.create(titulo="Velho", doi="10/leg", eh_legado=True)
    reg.artigo = legado
    reg.ja_no_acervo = True
    reg.save(update_fields=["artigo", "ja_no_acervo"])
    client.force_login(dono)
    client.post(
        reverse("triagem_busca_fonte", args=[proj_anco.slug, busca.pk]),
        data={"i": "0", "titulo": "Novo título", "resumo": "x", "doi": "10/leg"},
    )
    reg.refresh_from_db()
    legado.refresh_from_db()
    assert reg.titulo == "Novo título"  # registro muda
    assert legado.titulo == "Velho"  # legado intocado


def test_realce_marca_o_termo(client, proj_anco):
    dono = _user("donor")
    busca = Busca.objects.create(protocolo=proj_anco, criado_por=dono, outra_base="WoS")
    reg = RegistroTriagem.objects.create(
        protocolo=proj_anco,
        titulo="On cognitive analysis of learning",
        doi="10/realce",
        identificador="idr",
    )
    reg.origem_buscas.add(busca)
    client.force_login(dono)
    resp = client.get(reverse("triagem_busca_fonte", args=[proj_anco.slug, busca.pk]) + "?i=0")
    assert resp.status_code == 200
    assert b"<mark>cognitive analysis</mark>" in resp.content


def test_navegador_de_projeto_mostra_minhas_fontes(client, proj_anco):
    dono = _user("donp")
    outro = _user("outrop")
    b1 = Busca.objects.create(protocolo=proj_anco, criado_por=dono, outra_base="WoS")
    b2 = Busca.objects.create(protocolo=proj_anco, criado_por=outro, outra_base="Scopus")
    for k in range(2):
        r = RegistroTriagem.objects.create(
            protocolo=proj_anco,
            titulo=f"meu {k}",
            doi=f"10/meu{k}",
            identificador=f"meu{k}",
            status=RegistroTriagem.Status.INCLUIDO,
        )
        r.origem_buscas.add(b1)
    # Importação de outro analista (não deve aparecer para 'dono').
    ro = RegistroTriagem.objects.create(
        protocolo=proj_anco,
        titulo="outro",
        doi="10/outro",
        identificador="outro",
        status=RegistroTriagem.Status.INCLUIDO,
    )
    ro.origem_buscas.add(b2)

    client.force_login(dono)
    resp = client.get(reverse("triagem_fontes", args=[proj_anco.slug]) + "?i=0")
    assert resp.status_code == 200
    assert resp.context["total"] == 2  # só as fontes das bases que o dono importou


def test_nao_dono_nao_acessa_fontes(client, proj_anco):
    dono = _user("dono4")
    intruso = _user("intruso4")
    busca, _ = _busca_com_fontes(proj_anco, dono, 2)
    client.force_login(intruso)
    resp = client.get(reverse("triagem_busca_fonte", args=[proj_anco.slug, busca.pk]))
    assert resp.status_code == 403
