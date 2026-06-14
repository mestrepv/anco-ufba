"""Página do corpus (incluidos): resumo, status por item e filtros."""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.acervo.models import Analise
from apps.triagem.models import Busca, ProtocoloTriagem, RegistroTriagem
from apps.triagem.promocao import promover_para_acervo

from .conftest import membro

User = get_user_model()
pytestmark = pytest.mark.django_db


@pytest.fixture
def proj_anco(db):
    return ProtocoloTriagem.ativo()


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


def test_registros_renderiza_cards(client, proj_anco):
    """A página /registros/ usa o componente de linha unificado (sem 500) e
    mostra título + status de triagem de cada registro."""
    ana = _user("ana_reg")
    _incluido(proj_anco, "10/reg1", ano=2019)
    RegistroTriagem.objects.create(
        protocolo=proj_anco, titulo="Excluído X", doi="10/exc",
        status=RegistroTriagem.Status.EXCLUIDO,
    )
    client.force_login(ana)
    resp = client.get(reverse("triagem_registros", args=[proj_anco.slug]))
    assert resp.status_code == 200
    corpo = resp.content.decode()
    assert "Art 10/reg1" in corpo and "Excluído X" in corpo
    assert "al-chip" in corpo  # padrão visual unificado aplicado


def test_resumo_e_status_por_item(client, proj_anco):
    ana = _user("ana")
    _, art_sem = _incluido(proj_anco, "10/sem", ano=2010)
    _, art_an = _incluido(proj_anco, "10/an", ano=2020, tipo="Tese/Dissertação")
    _incluido(proj_anco, "10/c2", ano=2015)
    Analise.objects.create(artigo=art_an, analista=ana, status=Analise.Status.PUBLICADA)

    client.force_login(ana)
    resp = client.get(reverse("triagem_incluidos", args=[proj_anco.slug]))
    assert resp.status_code == 200
    assert resp.context["total"] == 3
    assert resp.context["n_analisado"] == 1
    assert resp.context["n_pendente"] == 0  # sem sorteio: ninguém "em análise/atribuído"
    assert resp.context["n_sem"] == 2
    assert resp.context["n_teses"] == 1
    assert resp.context["ano_min"] == 2010 and resp.context["ano_max"] == 2020
    corpo = resp.content.decode()
    assert "analisado" in corpo and "sem análise" in corpo
    # Opções de filtro sem duplicação (apesar de status de análise diferentes).
    assert resp.context["tipos"] == ["Artigo", "Tese/Dissertação"]
    assert len(resp.context["tipos"]) == len(set(resp.context["tipos"]))


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


def test_base_agrupa_importacoes_iguais(client, proj_anco):
    ana = _user("ana4")
    # Mesma base ("WoS") importada em 2 arquivos → 1 opção no filtro.
    b1 = Busca.objects.create(protocolo=proj_anco, criado_por=ana, outra_base="WoS")
    b2 = Busca.objects.create(protocolo=proj_anco, criado_por=ana, outra_base="WoS")
    reg1, _ = _incluido(proj_anco, "10/b1")
    reg2, _ = _incluido(proj_anco, "10/b2")
    reg1.origem_buscas.add(b1)
    reg2.origem_buscas.add(b2)
    _incluido(proj_anco, "10/sem-base")
    client.force_login(ana)
    resp = client.get(reverse("triagem_incluidos", args=[proj_anco.slug]))
    assert resp.context["bases"] == ["WoS"]  # uma só opção, sem duplicar
    # Filtrar por "WoS" traz os 2 registros das duas importações.
    resp2 = client.get(reverse("triagem_incluidos", args=[proj_anco.slug]), {"base": "WoS"})
    assert resp2.context["n_filtrado"] == 2


def test_marca_artigo_individual(client, proj_anco):
    from apps.acervo.models import Artigo
    from apps.triagem.promocao import registrar_artigo_no_corpus

    ana = _user("anaind")
    art = Artigo.objects.create(
        titulo="Ind", doi="10/indc", ano=2020, resumo="r", palavras_chaves="k"
    )
    registrar_artigo_no_corpus(proj_anco, art, ana)
    client.force_login(ana)
    resp = client.get(reverse("triagem_incluidos", args=[proj_anco.slug]))
    regs = list(resp.context["pagina"].object_list)
    assert regs[0].eh_individual is True
    assert b"individual" in resp.content


def test_busca_por_titulo(client, proj_anco):
    ana = _user("ana3")
    reg, _ = _incluido(proj_anco, "10/x")
    reg.titulo = "Cognitive analysis of memory"
    reg.save(update_fields=["titulo"])
    _incluido(proj_anco, "10/y")
    client.force_login(ana)
    resp = client.get(reverse("triagem_incluidos", args=[proj_anco.slug]), {"q": "memory"})
    assert resp.context["n_filtrado"] == 1
