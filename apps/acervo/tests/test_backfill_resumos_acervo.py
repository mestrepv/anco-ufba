"""Comando backfill_resumos_acervo — aplica em não-legado, propõe p/ legado."""

import csv
from io import StringIO
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.acervo.management.commands.backfill_resumos_acervo import _titulo_bate
from apps.acervo.models import Artigo

pytestmark = pytest.mark.django_db

ABSTRACT = (
    "Este artigo investiga o papel da emoção na tomada de decisão ética e "
    "propõe um modelo integrativo do comportamento antiético no trabalho."
)


def _art(titulo, resumo="", doi="10.1/a", legado=False):
    return Artigo.objects.create(titulo=titulo, ano=2023, doi=doi, resumo=resumo, eh_legado=legado)


# ---------------------------------------------------------------------------
# _titulo_bate
# ---------------------------------------------------------------------------


def test_titulo_bate_classifica():
    assert _titulo_bate("Cognição e emoção", "Cognição e emoção")[0] == "S"
    assert (
        _titulo_bate("Cognição e emoção", "Um estudo totalmente diferente sobre peixes")[0] == "N"
    )
    assert _titulo_bate("qualquer", "")[0] == "?"


# ---------------------------------------------------------------------------
# Modo aplicar (não-legado)
# ---------------------------------------------------------------------------


def _run_aplicar(titulo_ref, **opts):
    """Roda o comando mockando busca de abstract e título de referência."""
    out = StringIO()
    with (
        patch(
            "apps.acervo.management.commands.backfill_resumos_acervo.melhor_abstract",
            return_value=(ABSTRACT, "crossref"),
        ),
        patch(
            "apps.acervo.management.commands.backfill_resumos_acervo.lookup_doi",
        ) as look,
    ):
        look.return_value.encontrado = True
        look.return_value.dados = {"titulo": titulo_ref}
        call_command("backfill_resumos_acervo", stdout=out, **opts)
    return out.getvalue()


def test_preenche_nao_legado_quando_titulo_bate():
    art = _art("Modelo do afeto integral dominante", resumo="")
    _run_aplicar(titulo_ref="Modelo do afeto integral dominante")
    art.refresh_from_db()
    assert art.resumo == ABSTRACT


def test_trava_quando_titulo_diverge():
    art = _art("Modelo do afeto integral dominante", resumo="")
    _run_aplicar(titulo_ref="Reprodução de peixes em cativeiro na Amazônia")
    art.refresh_from_db()
    assert art.resumo == ""  # DOI suspeito → não grava


def test_nao_toca_legado_no_modo_aplicar():
    leg = _art("Obra legado", resumo="", legado=True)
    _run_aplicar(titulo_ref="Obra legado")
    leg.refresh_from_db()
    assert leg.resumo == ""  # legado nunca é candidato do modo aplicar


def test_dry_run_nao_grava():
    art = _art("Título X", resumo="")
    _run_aplicar(titulo_ref="Título X", dry_run=True)
    art.refresh_from_db()
    assert art.resumo == ""


# ---------------------------------------------------------------------------
# Modo proposta (legado)
# ---------------------------------------------------------------------------


def test_proposta_nao_grava_e_exporta_csv(tmp_path):
    leg_ok = _art("Cognição situada", resumo="", legado=True, doi="10.1/ok")
    leg_ruim = _art("Cognição situada", resumo="", legado=True, doi="10.1/ruim")
    caminho = str(tmp_path / "proposta.csv")

    def fake_lookup(doi):
        m = type("R", (), {})()
        m.encontrado = True
        # DOI 'ruim' devolve título de outro artigo (simula DOI errado)
        m.dados = {"titulo": "Cognição situada" if doi == "10.1/ok" else "Peixes da Amazônia"}
        return m

    out = StringIO()
    with (
        patch(
            "apps.acervo.management.commands.backfill_resumos_acervo.melhor_abstract",
            return_value=(ABSTRACT, "crossref"),
        ),
        patch(
            "apps.acervo.management.commands.backfill_resumos_acervo.lookup_doi",
            side_effect=fake_lookup,
        ),
    ):
        call_command("backfill_resumos_acervo", proposta=caminho, stdout=out)

    # Nada gravado no acervo.
    leg_ok.refresh_from_db()
    leg_ruim.refresh_from_db()
    assert leg_ok.resumo == "" and leg_ruim.resumo == ""

    # CSV com o veredito de título por linha.
    with open(caminho, encoding="utf-8") as fh:
        linhas = {row["doi"]: row for row in csv.DictReader(fh)}
    assert linhas["10.1/ok"]["titulo_bate"] == "S"
    assert linhas["10.1/ruim"]["titulo_bate"] == "N"
    assert linhas["10.1/ok"]["abstract_recuperado"] == ABSTRACT


def test_proposta_exige_extensao_csv():
    with pytest.raises(CommandError):
        call_command("backfill_resumos_acervo", proposta="/tmp/x.txt")
