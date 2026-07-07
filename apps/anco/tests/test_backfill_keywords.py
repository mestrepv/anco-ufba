"""Comando backfill_keywords — recupera palavras-chave vazias via DOI, com procedência."""

from io import StringIO
from unittest.mock import patch

import pytest
from django.core.management import call_command

from apps.acervo.models import Artigo
from apps.acervo.services.abstracts import melhor_keywords
from apps.anco.models import ItemCorpus, ProjetoANCO

pytestmark = pytest.mark.django_db


@pytest.fixture
def projeto(db):
    return ProjetoANCO.objects.create(nome="Piloto", slug="piloto-x", pergunta_pesquisa="Q?")


def _item(projeto, palavras="", doi="10.1/a", ident="k1", legado=False):
    art = Artigo.objects.create(
        titulo="Obra", ano=2023, doi=doi, palavras_chaves=palavras, eh_legado=legado
    )
    return ItemCorpus.objects.create(
        projeto=projeto,
        titulo="Obra",
        identificador=ident,
        doi=doi,
        palavras_chaves=palavras,
        artigo=art,
    )


# ---------------------------------------------------------------------------
# melhor_keywords — cascata Crossref subjects → OpenAlex keywords
# ---------------------------------------------------------------------------


def test_prefere_crossref_subjects():
    from apps.acervo.services._base import LookupResultado

    with (
        patch(
            "apps.acervo.services.abstracts.lookup_doi",
            return_value=LookupResultado(
                encontrado=True, dados={"palavras_chave": ["Cognição", "Memória"]}
            ),
        ),
        patch("apps.acervo.services.abstracts.keywords_por_doi", return_value=["X"]) as oa,
    ):
        termos, fonte = melhor_keywords("10.1/a")
    assert (termos, fonte) == (["Cognição", "Memória"], "crossref")
    oa.assert_not_called()


def test_cai_para_openalex_sem_subjects():
    from apps.acervo.services._base import LookupResultado

    with (
        patch(
            "apps.acervo.services.abstracts.lookup_doi",
            return_value=LookupResultado(encontrado=True, dados={"palavras_chave": []}),
        ),
        patch(
            "apps.acervo.services.abstracts.keywords_por_doi", return_value=["Cultural landscape"]
        ),
    ):
        termos, fonte = melhor_keywords("10.1/a")
    assert (termos, fonte) == (["Cultural landscape"], "openalex")


# ---------------------------------------------------------------------------
# Comando
# ---------------------------------------------------------------------------


def _run(**opts):
    out = StringIO()
    call_command("backfill_keywords", projeto="piloto-x", stdout=out, **opts)
    return out.getvalue()


def test_preenche_com_sufixo_de_procedencia(projeto):
    it = _item(projeto, palavras="", ident="v1")
    with patch(
        "apps.anco.management.commands.backfill_keywords.melhor_keywords",
        return_value=(["Cultural heritage", "Cultural landscape"], "openalex"),
    ):
        _run()
    it.refresh_from_db()
    it.artigo.refresh_from_db()
    assert it.palavras_chaves == "Cultural heritage; Cultural landscape — via OpenAlex"
    assert it.artigo.palavras_chaves == it.palavras_chaves  # propagado


def test_nao_sobrescreve_palavras_existentes(projeto):
    it = _item(projeto, palavras="palavra do autor", ident="c1")
    with patch(
        "apps.anco.management.commands.backfill_keywords.melhor_keywords",
        return_value=(["Outra"], "openalex"),
    ):
        saida = _run()
    it.refresh_from_db()
    assert it.palavras_chaves == "palavra do autor"
    assert "0 item(ns)" in saida  # não entra como alvo


def test_pula_legado(projeto):
    it = _item(projeto, palavras="", ident="l1", legado=True)
    with patch(
        "apps.anco.management.commands.backfill_keywords.melhor_keywords",
        return_value=(["Algo"], "openalex"),
    ):
        _run()
    it.refresh_from_db()
    assert it.palavras_chaves == ""  # legado nunca é alvo


def test_dry_run_nao_grava(projeto):
    it = _item(projeto, palavras="", ident="d1")
    with patch(
        "apps.anco.management.commands.backfill_keywords.melhor_keywords",
        return_value=(["Algo"], "crossref"),
    ):
        _run(dry_run=True)
    it.refresh_from_db()
    assert it.palavras_chaves == ""


def test_sem_keywords_nao_preenche(projeto):
    it = _item(projeto, palavras="", ident="s1")
    with patch(
        "apps.anco.management.commands.backfill_keywords.melhor_keywords",
        return_value=([], ""),
    ):
        _run()
    it.refresh_from_db()
    assert it.palavras_chaves == ""
