"""Artigo individual entra no corpus do projeto (vira fonte sorteável)."""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.acervo.models import Analise, Artigo
from apps.triagem.models import ProtocoloTriagem, RegistroTriagem
from apps.triagem.promocao import registrar_artigo_no_corpus
from apps.vocabulario.models import TermoVocabulario, Vocabulario

from .conftest import membro

User = get_user_model()
pytestmark = pytest.mark.django_db


@pytest.fixture
def proj_anco(db):
    p = ProtocoloTriagem.ativo()
    p.modo = ProtocoloTriagem.Modo.ANCO
    p.save()
    return p


@pytest.fixture
def base(db):
    v, _ = Vocabulario.objects.get_or_create(codigo="base", defaults={"nome": "Base"})
    return TermoVocabulario.objects.create(vocabulario=v, nome="Manual")


def _user(nome):
    return membro(
        User.objects.create_user(
            username=nome, email=f"{nome}@u.edu", password="x", papel=User.Papel.ANALISTA
        )
    )


def test_registrar_artigo_no_corpus_idempotente(proj_anco):
    u = _user("u1")
    art = Artigo.objects.create(
        titulo="Cognition", doi="10/ind1", ano=2020, resumo="r", palavras_chaves="k"
    )
    reg = registrar_artigo_no_corpus(proj_anco, art, u)
    assert reg.status == RegistroTriagem.Status.INCLUIDO
    assert reg.artigo_id == art.pk
    assert reg.origem_buscas.filter(criado_por=u, outra_base="Artigos individuais").exists()
    # idempotente: 2ª chamada reusa o mesmo registro.
    reg2 = registrar_artigo_no_corpus(proj_anco, art, u)
    assert reg2.pk == reg.pk
    assert proj_anco.registros.filter(artigo=art).count() == 1
    # contadores da Busca sintética coerentes (1, não 0 nem 2).
    busca = reg.origem_buscas.get(outra_base="Artigos individuais")
    busca.refresh_from_db()
    assert busca.n_lidos == 1 and busca.n_novos == 1


def test_registrar_legado_e_isento(proj_anco):
    u = _user("u2")
    leg = Artigo.objects.create(titulo="Velho", doi="10/leg", eh_legado=True)
    assert registrar_artigo_no_corpus(proj_anco, leg, u) is None
    assert not proj_anco.registros.filter(artigo=leg).exists()


def test_cadastro_com_projeto_vai_ao_corpus(client, proj_anco, base):
    u = _user("u3")
    client.force_login(u)
    resp = client.post(
        reverse("cadastrar_artigo") + f"?projeto={proj_anco.slug}",
        data={
            "titulo": "Cog individual",
            "ano": "2021",
            "doi": "10.1/ind",
            "link_acesso": "https://example.org/a",
            "base_consulta": str(base.pk),
            "tipo_publicacao": "artigo",
            "area": "Psicologia",
        },
    )
    assert resp.status_code == 302
    assert resp.url == reverse("triagem_incluidos", args=[proj_anco.slug])
    art = Artigo.objects.get(doi="10.1/ind")
    assert proj_anco.registros.filter(
        artigo=art, status=RegistroTriagem.Status.INCLUIDO
    ).exists()  # entrou no corpus
    assert not Analise.objects.filter(artigo=art).exists()  # NÃO iniciou análise


def test_cadastro_sem_projeto_inicia_analise(client, base):
    u = _user("u4")
    client.force_login(u)
    resp = client.post(
        reverse("cadastrar_artigo"),
        data={
            "titulo": "Cog avulso",
            "ano": "2021",
            "doi": "10.1/avulso",
            "link_acesso": "https://example.org/b",
            "base_consulta": str(base.pk),
            "tipo_publicacao": "artigo",
            "area": "Psicologia",
        },
    )
    assert resp.status_code == 302
    art = Artigo.objects.get(doi="10.1/avulso")
    assert Analise.objects.filter(artigo=art).exists()  # fluxo avulso inicia análise
    assert not ProtocoloTriagem.ativo().registros.filter(artigo=art).exists()  # fora do corpus
