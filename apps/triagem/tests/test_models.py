"""Fase 9.1 — modelos da triagem: dedup, constraints, singleton."""

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.utils import timezone

from apps.acervo.models import _gerar_identificador_interno
from apps.triagem.models import (
    Busca,
    DecisaoTriagem,
    ProtocoloTriagem,
    RegistroTriagem,
    chave_dedup,
)
from apps.vocabulario.models import TermoVocabulario, Vocabulario

User = get_user_model()
pytestmark = pytest.mark.django_db


@pytest.fixture
def protocolo(db):
    return ProtocoloTriagem.objects.create(titulo="P")


@pytest.fixture
def base_termo(db):
    v = Vocabulario.objects.create(codigo="base", nome="Base")
    return TermoVocabulario.objects.create(vocabulario=v, nome="Scopus")


# ---- chave_dedup -----------------------------------------------------------

def test_chave_dedup_prioriza_doi():
    assert chave_dedup("10.1/ABC", "123", "T", 2020, "P") == "doi:10.1/abc"


def test_chave_dedup_usa_isbn_sem_doi():
    assert chave_dedup("", "978-3-16-148410-0", "T", 2020, "P") == "isbn:9783161484100"


def test_chave_dedup_hash_sem_doi_nem_isbn():
    esperado = _gerar_identificador_interno("Título X", 2019, "Rev")
    assert chave_dedup(None, None, "Título X", 2019, "Rev") == esperado


# ---- ProtocoloTriagem.ativo (singleton) ------------------------------------

def test_seed_da_migracao_cria_singleton(db):
    # A migração 0002_seed_protocolo cria o protocolo único.
    assert ProtocoloTriagem.objects.count() == 1
    assert ProtocoloTriagem.objects.first().n_revisores == 2


def test_ativo_cria_quando_vazio(db):
    ProtocoloTriagem.objects.all().delete()
    p = ProtocoloTriagem.ativo()
    assert p.pk is not None
    assert ProtocoloTriagem.objects.count() == 1


def test_ativo_reusa_o_de_menor_id(db):
    ProtocoloTriagem.objects.all().delete()
    primeiro = ProtocoloTriagem.objects.create(titulo="P1")
    ProtocoloTriagem.objects.create(titulo="P2")
    assert ProtocoloTriagem.ativo().pk == primeiro.pk


# ---- RegistroTriagem -------------------------------------------------------

def test_registro_gera_identificador_no_save(protocolo):
    r = RegistroTriagem.objects.create(protocolo=protocolo, titulo="T", doi="10.5/XY")
    assert r.identificador == "doi:10.5/xy"


def test_registro_unico_por_identificador_no_protocolo(protocolo):
    RegistroTriagem.objects.create(protocolo=protocolo, titulo="A", doi="10.9/z")
    with pytest.raises(IntegrityError):
        RegistroTriagem.objects.create(protocolo=protocolo, titulo="B", doi="10.9/z")


def test_mesmo_identificador_em_protocolos_distintos_ok(protocolo):
    outro = ProtocoloTriagem.objects.create(titulo="Q")
    RegistroTriagem.objects.create(protocolo=protocolo, titulo="A", doi="10.9/z")
    # mesma chave, protocolo diferente → permitido
    r = RegistroTriagem.objects.create(protocolo=outro, titulo="A", doi="10.9/z")
    assert r.pk is not None


def test_origem_buscas_m2m(protocolo, base_termo):
    b = Busca.objects.create(protocolo=protocolo, base_consulta=base_termo)
    r = RegistroTriagem.objects.create(protocolo=protocolo, titulo="A", doi="10.1/a")
    r.origem_buscas.add(b)
    assert list(r.origem_buscas.all()) == [b]
    assert b.base_nome == "Scopus"


# ---- DecisaoTriagem --------------------------------------------------------

def test_decisao_unica_por_revisor_registro(protocolo):
    rev = User.objects.create_user(username="r", email="r@u.edu", password="x")
    reg = RegistroTriagem.objects.create(protocolo=protocolo, titulo="A", doi="10.1/a")
    prazo = timezone.now()
    DecisaoTriagem.objects.create(registro=reg, revisor=rev, prazo_em=prazo)
    with pytest.raises(IntegrityError):
        DecisaoTriagem.objects.create(registro=reg, revisor=rev, prazo_em=prazo)
