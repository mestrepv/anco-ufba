"""Teste de fluxo ponta a ponta da triagem com um arquivo RIS real.

Roda **no banco de teste** (isolado e revertido ao fim) — não toca o acervo de
produção. O arquivo é lido de `TRIAGEM_RIS_PATH` (default `/tmp/wos.ris`); o teste
é **pulado** se o arquivo não estiver presente, então é seguro versionar.

Exercita: importação + dedup → sorteio de ≥2 revisores → decisões (consenso de
inclusão/exclusão e divergência) → desempate do curador → promoção dos incluídos
a `Artigo` → contagens PRISMA.
"""

import os
from pathlib import Path

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.acervo.models import Artigo
from apps.triagem import prisma
from apps.triagem.aprovacao import registros_para_desempate
from apps.triagem.importacao import decodificar, importar_para_busca, parse_ris
from apps.triagem.models import (
    Busca,
    DecisaoTriagem,
    ProtocoloTriagem,
    RegistroTriagem,
)
from apps.triagem.promocao import promover_para_acervo
from apps.triagem.tasks import iniciar_triagem

from .conftest import membro

User = get_user_model()

RIS_PATH = Path(os.environ.get("TRIAGEM_RIS_PATH", "/tmp/wos.ris"))

pytestmark = [
    pytest.mark.django_db,
    pytest.mark.skipif(not RIS_PATH.exists(), reason=f"RIS ausente: {RIS_PATH}"),
]


def _revisor(n):
    return membro(
        User.objects.create_user(
            username=f"rv{n}",
            email=f"rv{n}@u.edu",
            password="x",
            papel=User.Papel.ANALISTA,
            revisor_aprovado=True,
            aceita_revisoes=True,
            limite_revisoes_simultaneas=500,
        )
    )


def _decide(registro, revisor, decisao):
    d = DecisaoTriagem.objects.get(registro=registro, revisor=revisor)
    d.decisao = decisao
    if decisao == RegistroTriagem.Decisao.EXCLUIR:
        d.motivo_exclusao = "fora de escopo"
    d.concluido_em = timezone.now()
    d.save()  # signal (sync) → avaliação → promoção em consenso de inclusão


def test_fluxo_completo_com_ris_real(capsys):
    protocolo = ProtocoloTriagem.ativo()
    coletor = User.objects.create_user(
        username="coletor", email="col@u.edu", password="x", papel=User.Papel.ANALISTA
    )
    curador = User.objects.create_user(
        username="cur",
        email="cur@u.edu",
        password="x",
        papel=User.Papel.CURADOR,
        is_staff=True,
    )
    for i in range(3):  # pool de revisores aprovados para o sorteio
        _revisor(i)

    # 1) Parse + importação ------------------------------------------------
    brutos = parse_ris(decodificar(RIS_PATH.read_bytes()))
    assert len(brutos) >= 40, "esperava dezenas de registros no RIS"
    # campos essenciais mapeados no 1º registro
    assert brutos[0]["titulo"]
    assert brutos[0]["titulo_periodico"]

    busca = Busca.objects.create(
        protocolo=protocolo,
        outra_base="Web of Science",
        formato="ris",
        criado_por=coletor,
    )
    res = importar_para_busca(busca, brutos)
    assert res.total == len(brutos)
    assert res.criados >= 1
    n_registros = RegistroTriagem.objects.filter(protocolo=protocolo).count()
    assert n_registros == res.criados + res.ja_no_acervo  # únicos no protocolo

    # 2) Curador inicia a triagem (sorteio de 2 revisores por registro) ----
    enfileirados = iniciar_triagem(protocolo)
    assert enfileirados == n_registros  # nenhum ja_no_acervo no banco de teste
    em_triagem = RegistroTriagem.objects.filter(
        protocolo=protocolo, status=RegistroTriagem.Status.EM_TRIAGEM
    )
    assert em_triagem.count() == n_registros
    for reg in em_triagem:
        assert reg.decisoes.count() == protocolo.n_revisores  # 2 revisores

    # 3) Decisões: ~incluir maioria, excluir alguns, divergir alguns -------
    registros = list(em_triagem)
    n_inc = n_exc = n_div = 0
    for i, reg in enumerate(registros):
        decs = list(reg.decisoes.all())
        if i % 7 == 0:  # divergência
            _decide(reg, decs[0].revisor, RegistroTriagem.Decisao.INCLUIR)
            _decide(reg, decs[1].revisor, RegistroTriagem.Decisao.EXCLUIR)
            n_div += 1
        elif i % 3 == 0:  # consenso de exclusão
            for d in decs:
                _decide(reg, d.revisor, RegistroTriagem.Decisao.EXCLUIR)
            n_exc += 1
        else:  # consenso de inclusão
            for d in decs:
                _decide(reg, d.revisor, RegistroTriagem.Decisao.INCLUIR)
            n_inc += 1

    # 4) Verifica consenso + promoção automática dos incluídos -------------
    incluidos = RegistroTriagem.objects.filter(
        protocolo=protocolo, status=RegistroTriagem.Status.INCLUIDO
    )
    excluidos = RegistroTriagem.objects.filter(
        protocolo=protocolo, status=RegistroTriagem.Status.EXCLUIDO
    )
    assert incluidos.count() == n_inc
    assert excluidos.count() == n_exc
    for reg in incluidos:
        assert reg.artigo_id is not None, "incluído deve virar Artigo"
        assert reg.artigo.eh_legado is False

    # 5) Desempate do curador resolve as divergências ----------------------
    pendentes = registros_para_desempate(protocolo)
    assert len(pendentes) == n_div
    for reg in pendentes:
        reg.status = RegistroTriagem.Status.INCLUIDO
        reg.decisao_final = RegistroTriagem.Decisao.INCLUIR
        reg.decidida_por = curador
        reg.decidida_em = timezone.now()
        reg.save()
        promover_para_acervo(reg)

    assert not registros_para_desempate(protocolo)  # nada mais pendente
    total_incluidos = RegistroTriagem.objects.filter(
        protocolo=protocolo, status=RegistroTriagem.Status.INCLUIDO
    ).count()
    # todo incluído tem Artigo; nenhum em triagem sobrou
    assert (
        RegistroTriagem.objects.filter(
            protocolo=protocolo, status=RegistroTriagem.Status.EM_TRIAGEM
        ).count()
        == 0
    )
    artigos_promovidos = Artigo.objects.filter(registros_triagem__isnull=False).distinct().count()
    assert artigos_promovidos == total_incluidos

    # 6) Contagens PRISMA coerentes ----------------------------------------
    c = prisma.computar(protocolo)
    assert c.importados == n_registros
    assert c.incluidos == total_incluidos
    assert c.elegiveis == c.incluidos + c.excluidos + c.aguardando + c.em_triagem

    # ── resumo legível ────────────────────────────────────────────────
    with capsys.disabled():
        print("\n──────── FLUXO DE TRIAGEM (RIS real, banco de teste) ────────")
        print(f"  lidos do RIS .......... {res.total}")
        print(f"  registros únicos ...... {n_registros} (duplicados mesclados: {res.duplicados})")
        print(f"  sem DOI (hash) ........ {sum(1 for b in brutos if not b['doi'])}")
        print(f"  sorteados p/ triagem .. {enfileirados} (×{protocolo.n_revisores} revisores)")
        print(f"  consenso incluir ...... {n_inc}")
        print(f"  consenso excluir ...... {n_exc}")
        print(f"  divergentes ........... {n_div} → desempate → incluídos")
        print(f"  INCLUÍDOS (→ Artigo) .. {total_incluidos}")
        print(f"  EXCLUÍDOS ............. {c.excluidos}")
        print("  PRISMA:", c.como_dict())
        print("  acervo de produção: NÃO tocado (banco de teste, revertido).")
        print("─────────────────────────────────────────────────────────────")
