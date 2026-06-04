"""Fase 10.2 — possíveis duplicatas por similaridade (pg_trgm)."""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.triagem import duplicatas as dup
from apps.triagem.models import (
    DecisaoTriagem,
    ParDuplicataDescartado,
    ProtocoloTriagem,
    RegistroTriagem,
)
from apps.triagem.sorteio import executar_sorteio

User = get_user_model()
pytestmark = pytest.mark.django_db


@pytest.fixture
def protocolo(db):
    return ProtocoloTriagem.ativo()


def _reg(protocolo, titulo, doi=""):
    return RegistroTriagem.objects.create(protocolo=protocolo, titulo=titulo, doi=doi)


@pytest.fixture
def analista(db):
    return User.objects.create_user(
        username="ana", email="a@u.edu", password="x", papel=User.Papel.ANALISTA
    )


def test_detecta_titulos_semelhantes_sem_doi(protocolo):
    _reg(protocolo, "Aprendizagem cognitiva no ensino de ciências")
    _reg(protocolo, "Aprendizagem cognitiva no ensino de ciencias")  # sem acento
    _reg(protocolo, "Tópico totalmente diferente sobre robótica")
    pares = dup.pares_possiveis(protocolo, limiar=0.4)
    assert len(pares) == 1
    titulos = {pares[0]["a"].titulo, pares[0]["b"].titulo}
    assert any("ciências" in t or "ciencias" in t for t in titulos)


def test_mesclar_marca_duplicado_e_funde_origens(protocolo):
    a = _reg(protocolo, "Mesmo artigo sobre metacognição")
    b = _reg(protocolo, "Mesmo artigo sobre metacognicao")
    dup.mesclar(a, b)
    b.refresh_from_db()
    assert b.status == RegistroTriagem.Status.DUPLICADO
    assert b.duplicado_de_id == a.pk


def test_duplicado_nao_e_sorteado(protocolo):
    a = _reg(protocolo, "Artigo X sobre cognição")
    b = _reg(protocolo, "Artigo X sobre cognicao")
    dup.mesclar(a, b)
    # revisores aprovados suficientes
    for i in range(2):
        User.objects.create_user(
            username=f"r{i}", email=f"r{i}@u.edu", password="x",
            papel=User.Papel.ANALISTA, revisor_aprovado=True, aceita_revisoes=True,
        )
    res = executar_sorteio(b)
    assert res.criadas == 0
    assert DecisaoTriagem.objects.filter(registro=b).count() == 0


def test_descartar_remove_do_resultado(protocolo):
    a = _reg(protocolo, "Cognição e linguagem na escola")
    b = _reg(protocolo, "Cognicao e linguagem na escola")
    assert len(dup.pares_possiveis(protocolo, limiar=0.4)) == 1
    dup.descartar(a, b)
    assert ParDuplicataDescartado.objects.count() == 1
    assert len(dup.pares_possiveis(protocolo, limiar=0.4)) == 0


def test_view_mesclar(client, protocolo, analista):
    a = _reg(protocolo, "Título praticamente igual aqui")
    b = _reg(protocolo, "Titulo praticamente igual aqui")
    client.force_login(analista)
    resp = client.post(
        reverse("triagem_duplicata_mesclar"), data={"a": a.pk, "b": b.pk}
    )
    assert resp.status_code == 302
    b.refresh_from_db()
    assert b.status == RegistroTriagem.Status.DUPLICADO


def test_view_duplicatas_renderiza(client, protocolo, analista):
    _reg(protocolo, "Texto sobre aprendizagem situada")
    _reg(protocolo, "Texto sobre aprendizagem situada!")
    client.force_login(analista)
    resp = client.get(reverse("triagem_duplicatas"))
    assert resp.status_code == 200
