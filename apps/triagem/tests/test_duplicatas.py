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


def test_view_selecionar_este_mantem_o_escolhido(client, protocolo, analista):
    a = _reg(protocolo, "Título praticamente igual aqui", doi="10.1/aa")
    b = _reg(protocolo, "Titulo praticamente igual aqui", doi="10.1/bb")
    client.force_login(analista)
    # "Selecionar este" no registro A: mantém A, marca B como duplicata
    resp = client.post(
        reverse("triagem_duplicata_mesclar"),
        data={"manter": a.pk, "duplicado": b.pk, "i": 0},
    )
    assert resp.status_code == 302
    a.refresh_from_db()
    b.refresh_from_db()
    assert b.status == RegistroTriagem.Status.DUPLICADO
    assert b.duplicado_de_id == a.pk
    assert a.status != RegistroTriagem.Status.DUPLICADO


def test_navegar_sem_decidir(client, protocolo, analista):
    # dois pares distintos
    _reg(protocolo, "Aprendizagem ativa em sala", doi="10.2/a")
    _reg(protocolo, "Aprendizagem ativa em sala!", doi="10.2/b")
    _reg(protocolo, "Memória de trabalho e leitura", doi="10.3/a")
    _reg(protocolo, "Memória de trabalho e leitura!", doi="10.3/b")
    client.force_login(analista)
    r0 = client.get(reverse("triagem_duplicatas"))
    assert r0.context["total"] == 2
    assert r0.context["i"] == 0
    assert r0.context["tem_proximo"] is True
    # pular para o próximo sem decidir
    r1 = client.get(reverse("triagem_duplicatas"), {"i": 1})
    assert r1.context["i"] == 1
    assert r1.context["tem_proximo"] is False
    assert r1.context["tem_anterior"] is True
    # nenhuma decisão foi tomada
    from apps.triagem.models import RegistroTriagem as RT
    assert not RT.objects.filter(status=RT.Status.DUPLICADO).exists()


def test_view_duplicatas_renderiza(client, protocolo, analista):
    _reg(protocolo, "Texto sobre aprendizagem situada")
    _reg(protocolo, "Texto sobre aprendizagem situada!")
    client.force_login(analista)
    resp = client.get(reverse("triagem_duplicatas"))
    assert resp.status_code == 200


def test_primeiro_autor():
    assert dup.primeiro_autor("Roubekas, NP; Outro, X") == "Roubekas"
    assert dup.primeiro_autor("Bowden, H") == "Bowden"
    assert dup.mesmo_primeiro_autor("Silva, J", "silva, joão") is True
    assert dup.mesmo_primeiro_autor("Roubekas, NP", "Bowden, H") is False


def test_ordena_provaveis_duplicatas_primeiro(protocolo):
    # par forte: mesmo título, ano e autor (DOIs diferentes → não casou na chave)
    f1 = RegistroTriagem.objects.create(
        protocolo=protocolo, titulo="Cognição e cultura na Antiguidade", doi="10.1/a",
        ano=2020, autores="Silva, J",
    )
    f2 = RegistroTriagem.objects.create(
        protocolo=protocolo, titulo="Cognição e cultura na Antiguidade", doi="10.1/b",
        ano=2020, autores="Silva, J",
    )
    # par fraco: mesmo título, anos e autores diferentes (obra × resenha)
    RegistroTriagem.objects.create(
        protocolo=protocolo, titulo="Divinação e mente no mundo grego", doi="10.2/c",
        ano=2019, autores="Souza, M",
    )
    RegistroTriagem.objects.create(
        protocolo=protocolo, titulo="Divinação e mente no mundo grego", doi="10.2/d",
        ano=2024, autores="Lima, P",
    )
    pares = dup.pares_possiveis(protocolo, limiar=0.5)
    assert len(pares) == 2
    # o par com ano+autor concordando vem primeiro
    primeiro = pares[0]
    assert {primeiro["a"].pk, primeiro["b"].pk} == {f1.pk, f2.pk}


def test_view_avisa_provavel_distinto(client, protocolo, analista):
    RegistroTriagem.objects.create(
        protocolo=protocolo, titulo="A Cognitive Analysis of Divination", doi="10.3/a",
        ano=2025, autores="Roubekas, NP",
    )
    RegistroTriagem.objects.create(
        protocolo=protocolo, titulo="A Cognitive Analysis of Divination", doi="10.3/b",
        ano=2024, autores="Bowden, H",
    )
    client.force_login(analista)
    resp = client.get(reverse("triagem_duplicatas"))
    assert resp.status_code == 200
    assert "Provavelmente NÃO são duplicatas".encode() in resp.content
    assert b"autores diferentes" in resp.content
