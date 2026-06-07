"""Fase 9.5 — promoção de incluídos a Artigo (idempotente; legado intocado)."""

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.acervo.models import Analise, Artigo
from apps.triagem.models import (
    Busca,
    DecisaoTriagem,
    ProtocoloTriagem,
    RegistroTriagem,
)
from apps.triagem.promocao import promover_para_acervo
from apps.triagem.sorteio import executar_sorteio
from apps.vocabulario.models import TermoVocabulario, Vocabulario

from .conftest import membro

User = get_user_model()
pytestmark = pytest.mark.django_db


@pytest.fixture
def protocolo(db):
    return ProtocoloTriagem.ativo()


@pytest.fixture
def base_termo(db):
    v, _ = Vocabulario.objects.get_or_create(codigo="base", defaults={"nome": "Base"})
    return TermoVocabulario.objects.create(vocabulario=v, nome="Scopus")


def _revisores(n=2):
    return [
        membro(
            User.objects.create_user(
                username=f"rv{i}",
                email=f"rv{i}@u.edu",
                password="x",
                papel=User.Papel.ANALISTA,
                revisor_aprovado=True,
                aceita_revisoes=True,
            )
        )
        for i in range(n)
    ]


def test_promove_incluido_cria_artigo(protocolo, base_termo):
    b = Busca.objects.create(protocolo=protocolo, base_consulta=base_termo)
    reg = RegistroTriagem.objects.create(
        protocolo=protocolo,
        titulo="Novo artigo",
        doi="10.55/novo",
        ano=2021,
        idioma="english",
        status=RegistroTriagem.Status.INCLUIDO,
    )
    reg.origem_buscas.add(b)
    artigo = promover_para_acervo(reg)
    assert artigo is not None
    assert artigo.doi == "10.55/novo"
    assert artigo.eh_legado is False
    assert artigo.idioma == "en"
    assert artigo.base_consulta_id == base_termo.pk
    reg.refresh_from_db()
    assert reg.artigo_id == artigo.pk


def test_promocao_idempotente(protocolo):
    reg = RegistroTriagem.objects.create(
        protocolo=protocolo,
        titulo="X",
        doi="10.55/x",
        status=RegistroTriagem.Status.INCLUIDO,
    )
    a1 = promover_para_acervo(reg)
    a2 = promover_para_acervo(reg)
    assert a1.pk == a2.pk
    assert Artigo.objects.filter(doi="10.55/x").count() == 1


def test_so_promove_incluido(protocolo):
    reg = RegistroTriagem.objects.create(
        protocolo=protocolo,
        titulo="Y",
        doi="10.55/y",
        status=RegistroTriagem.Status.EM_TRIAGEM,
    )
    assert promover_para_acervo(reg) is None
    assert not Artigo.objects.filter(doi="10.55/y").exists()


def test_consenso_incluir_promove_via_signal(protocolo, base_termo):
    reg = RegistroTriagem.objects.create(protocolo=protocolo, titulo="Auto", doi="10.55/auto")
    _revisores(2)
    executar_sorteio(reg)
    for d in DecisaoTriagem.objects.filter(registro=reg):
        d.decisao = RegistroTriagem.Decisao.INCLUIR
        d.concluido_em = timezone.now()
        d.save()  # signal → avaliar → promove
    reg.refresh_from_db()
    assert reg.status == RegistroTriagem.Status.INCLUIDO
    assert reg.artigo_id is not None
    # disponível para análise pelo fluxo existente
    assert Artigo.objects.filter(pk=reg.artigo_id).exists()


def test_legado_intocado(protocolo, base_termo):
    legado = Artigo.objects.create(
        doi="10.99/legado",
        titulo="Obra legada",
        ano=2010,
        base_consulta=base_termo,
        eh_legado=True,
    )
    leitor = User.objects.create_user(
        username="leg", email="leg@u.edu", password="x", papel=User.Papel.ANALISTA
    )
    Analise.objects.create(artigo=legado, analista=leitor, status=Analise.Status.LEGADO)
    antes_total = Artigo.objects.count()

    reg = RegistroTriagem.objects.create(
        protocolo=protocolo,
        titulo="Outro",
        doi="10.99/outro",
        status=RegistroTriagem.Status.INCLUIDO,
    )
    novo = promover_para_acervo(reg)
    assert novo.pk != legado.pk
    assert Artigo.objects.count() == antes_total + 1
    legado.refresh_from_db()
    assert legado.eh_legado is True  # legado não foi alterado
