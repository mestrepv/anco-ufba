"""Fase 10.2 — possíveis duplicatas por similaridade (pg_trgm)."""

import pytest
from django.contrib.auth import get_user_model

from apps.triagem import duplicatas as dup
from apps.triagem.models import (
    DecisaoTriagem,
    ParDuplicataDescartado,
    ProtocoloTriagem,
    RegistroTriagem,
)
from apps.triagem.sorteio import executar_sorteio

from .conftest import membro, turl

User = get_user_model()
pytestmark = pytest.mark.django_db


@pytest.fixture
def protocolo(db):
    return ProtocoloTriagem.ativo()


def _reg(protocolo, titulo, doi=""):
    return RegistroTriagem.objects.create(protocolo=protocolo, titulo=titulo, doi=doi)


@pytest.fixture
def analista(db):
    # Curador do projeto: resolve qualquer par (testes de mecânica da dedup).
    return membro(User.objects.create_user(
        username="ana", email="a@u.edu", password="x", papel=User.Papel.ANALISTA
    ), papel="curador")


def _com_dono(protocolo, titulo, doi, dono):
    """Registro cuja base de origem foi importada por `dono`."""
    from apps.triagem.models import Busca

    r = _reg(protocolo, titulo, doi)
    b = Busca.objects.create(protocolo=protocolo, criado_por=dono)
    r.origem_buscas.add(b)
    return r


def _analista(nome):
    return membro(User.objects.create_user(
        username=nome, email=f"{nome}@u.edu", password="x", papel=User.Papel.ANALISTA
    ))


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
        turl("triagem_duplicata_mesclar"),
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
    r0 = client.get(turl("triagem_duplicatas"), {"escopo": "todas"})
    assert r0.context["total"] == 2
    assert r0.context["i"] == 0
    assert r0.context["tem_proximo"] is True
    # pular para o próximo sem decidir
    r1 = client.get(turl("triagem_duplicatas"), {"i": 1, "escopo": "todas"})
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
    resp = client.get(turl("triagem_duplicatas"))
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


def test_mesclar_grava_autor_e_data(protocolo, analista):
    a = _reg(protocolo, "Cognição distribuída e ferramentas")
    b = _reg(protocolo, "Cognicao distribuida e ferramentas")
    dup.mesclar(a, b, por=analista)
    b.refresh_from_db()
    assert b.duplicado_por_id == analista.pk
    assert b.duplicado_em is not None


def test_descartar_grava_autor(protocolo, analista):
    a = _reg(protocolo, "Atenção seletiva e leitura")
    b = _reg(protocolo, "Atencao seletiva e leitura")
    dup.descartar(a, b, por=analista)
    par = ParDuplicataDescartado.objects.get()
    assert par.criado_por_id == analista.pk


def test_desfazer_mescla_reabre_e_separa_origens(protocolo):
    from apps.triagem.models import Busca

    a = _reg(protocolo, "Metacognição na resolução de problemas")
    b = _reg(protocolo, "Metacognicao na resolucao de problemas")
    busca_b = Busca.objects.create(protocolo=protocolo)
    b.origem_buscas.add(busca_b)
    dup.mesclar(a, b)
    assert busca_b in a.origem_buscas.all()  # origem fundida

    assert dup.desfazer_mescla(b) is True
    b.refresh_from_db()
    assert b.status == RegistroTriagem.Status.IDENTIFICADO
    assert b.duplicado_de_id is None
    assert b.duplicado_por_id is None
    assert busca_b not in a.origem_buscas.all()  # origem devolvida
    # volta a aparecer como possível duplicata
    assert len(dup.pares_possiveis(protocolo, limiar=0.4)) == 1


def test_desfazer_mescla_nao_duplicata_retorna_false(protocolo):
    a = _reg(protocolo, "Qualquer título aqui")
    assert dup.desfazer_mescla(a) is False


def test_mescladas_lista_e_view(client, protocolo, analista):
    a = _reg(protocolo, "Carga cognitiva e multimídia", doi="10.9/a")
    b = _reg(protocolo, "Carga cognitiva e multimidia", doi="10.9/b")
    dup.mesclar(a, b, por=analista)
    assert list(dup.mescladas(protocolo)) == [b]

    client.force_login(analista)
    resp = client.get(turl("triagem_duplicatas_mescladas"))
    assert resp.status_code == 200
    # desfazer pela view
    resp2 = client.post(
        turl("triagem_duplicata_desfazer"), data={"duplicado": b.pk}
    )
    assert resp2.status_code == 302
    b.refresh_from_db()
    assert b.status == RegistroTriagem.Status.IDENTIFICADO


def test_procedencia_mostra_base_e_importador(protocolo):
    from apps.triagem.models import Busca

    importador = User.objects.create_user(
        username="imp", email="imp@u.edu", password="x",
        papel=User.Papel.ANALISTA, nome_exibicao="Importador Teste",
    )
    busca = Busca.objects.create(
        protocolo=protocolo, outra_base="Scopus", criado_por=importador
    )
    r = _reg(protocolo, "Artigo com procedência")
    r.origem_buscas.add(busca)
    proc = r.procedencia
    assert proc == [{"base": "Scopus", "por": "Importador Teste"}]


def test_dedup_gate_analista_ve_so_pares_que_importou(client, protocolo):
    importador = _analista("imp")
    outro = _analista("out")
    _com_dono(protocolo, "Título igual sobre cognição distribuída", "10.5/a", importador)
    _com_dono(protocolo, "Titulo igual sobre cognicao distribuida", "10.5/b", importador)
    client.force_login(importador)
    assert client.get(turl("triagem_duplicatas")).context["total"] == 1
    client.force_login(outro)  # não importou → não vê o par
    assert client.get(turl("triagem_duplicatas")).context["total"] == 0


def test_dedup_gate_nao_dono_recebe_403(client, protocolo):
    importador = _analista("imp")
    intruso = _analista("intru")
    a = _com_dono(protocolo, "Atenção e memória de trabalho", "10.6/a", importador)
    b = _com_dono(protocolo, "Atencao e memoria de trabalho", "10.6/b", importador)
    client.force_login(intruso)
    resp = client.post(
        turl("triagem_duplicata_mesclar"),
        data={"manter": a.pk, "duplicado": b.pk, "i": 0},
    )
    assert resp.status_code == 403
    b.refresh_from_db()
    assert b.status != RegistroTriagem.Status.DUPLICADO


def test_contar_pares_do_usuario_respeita_o_gate(protocolo):
    # Pares de uma base importada por OUTRO usuário.
    dono = _analista("dono")
    intruso = _analista("intru2")
    _com_dono(protocolo, "Cognição situada e prática docente", "10.8/a", dono)
    _com_dono(protocolo, "Cognicao situada e pratica docente", "10.8/b", dono)
    # Contagem total = 1; mas o intruso (não importou, não curador) vê 0.
    assert dup.contar_pares_possiveis(protocolo) == 1
    assert dup.contar_pares_do_usuario(protocolo, intruso, eh_curador=False) == 0
    assert dup.contar_pares_do_usuario(protocolo, dono, eh_curador=False) == 1
    assert dup.contar_pares_do_usuario(protocolo, intruso, eh_curador=True) == 1


def test_dedup_gate_curador_resolve_qualquer_par(client, protocolo):
    importador = _analista("imp")
    curador = membro(User.objects.create_user(
        username="cur", email="cur@u.edu", password="x", papel=User.Papel.CURADOR
    ), papel="curador")
    a = _com_dono(protocolo, "Aprendizagem por descoberta guiada", "10.7/a", importador)
    b = _com_dono(protocolo, "Aprendizagem por descoberta guiada!", "10.7/b", importador)
    client.force_login(curador)
    assert client.get(turl("triagem_duplicatas"), {"escopo": "todas"}).context["total"] == 1  # vê tudo
    resp = client.post(
        turl("triagem_duplicata_mesclar"),
        data={"manter": a.pk, "duplicado": b.pk, "i": 0},
    )
    assert resp.status_code == 302
    b.refresh_from_db()
    assert b.status == RegistroTriagem.Status.DUPLICADO


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
    resp = client.get(turl("triagem_duplicatas"), {"escopo": "todas"})
    assert resp.status_code == 200
    assert "Provavelmente NÃO são duplicatas".encode() in resp.content
    assert b"autores diferentes" in resp.content
