"""Comando backfill_resumos — recuperação de resumos truncados/vazios via DOI."""

from io import StringIO
from unittest.mock import patch

import pytest
from django.core.management import call_command

from apps.acervo.models import Artigo
from apps.acervo.services._base import LookupResultado
from apps.anco.management.commands.backfill_resumos import (
    _esta_truncado,
    buscar_abstract,
)
from apps.anco.models import ItemCorpus, ProjetoANCO

pytestmark = pytest.mark.django_db

ABSTRACT_COMPLETO = (
    "Este artigo investiga o papel da emoção na tomada de decisão ética, "
    "propondo o modelo do afeto integral dominante e discutindo suas "
    "implicações para o comportamento antiético no trabalho."
)


@pytest.fixture
def projeto(db):
    return ProjetoANCO.objects.create(nome="Piloto ANCO", pergunta_pesquisa="Q?")


def _item(projeto, resumo, doi="10.1/a", titulo="Obra", ident="k1", com_artigo=True):
    artigo = None
    if com_artigo:
        artigo = Artigo.objects.create(titulo=titulo, ano=2023, doi=doi, resumo=resumo)
    return ItemCorpus.objects.create(
        projeto=projeto,
        titulo=titulo,
        identificador=ident,
        doi=doi,
        resumo=resumo,
        artigo=artigo,
    )


# ---------------------------------------------------------------------------
# _esta_truncado
# ---------------------------------------------------------------------------


def test_deteccao_de_truncado():
    assert _esta_truncado("... rationally ...")
    assert _esta_truncado("texto cortado …")
    assert not _esta_truncado("Abstract completo e bem formado.")
    assert not _esta_truncado("")


# ---------------------------------------------------------------------------
# buscar_abstract — cascata Crossref → OpenAlex
# ---------------------------------------------------------------------------


def test_usa_crossref_quando_completo():
    with (
        patch(
            "apps.acervo.services.abstracts.lookup_doi",
            return_value=LookupResultado(encontrado=True, dados={"resumo": ABSTRACT_COMPLETO}),
        ),
        patch(
            "apps.acervo.services.abstracts.abstract_por_doi", return_value=""
        ) as oa,
    ):
        texto, fonte = buscar_abstract("10.1/a")
    assert fonte == "crossref"
    assert texto == ABSTRACT_COMPLETO
    oa.assert_called_once()  # tenta OpenAlex também, mas Crossref vence por tamanho


def test_cai_para_openalex_quando_crossref_vazio():
    with (
        patch(
            "apps.acervo.services.abstracts.lookup_doi",
            return_value=LookupResultado(encontrado=False, erro="404"),
        ),
        patch(
            "apps.acervo.services.abstracts.abstract_por_doi",
            return_value=ABSTRACT_COMPLETO,
        ),
    ):
        texto, fonte = buscar_abstract("10.1/a")
    assert fonte == "openalex"
    assert texto == ABSTRACT_COMPLETO


def test_ignora_crossref_truncado_e_usa_openalex():
    with (
        patch(
            "apps.acervo.services.abstracts.lookup_doi",
            return_value=LookupResultado(encontrado=True, dados={"resumo": "snippet ..."}),
        ),
        patch(
            "apps.acervo.services.abstracts.abstract_por_doi",
            return_value=ABSTRACT_COMPLETO,
        ),
    ):
        texto, fonte = buscar_abstract("10.1/a")
    assert fonte == "openalex"


def test_sem_abstract_em_lugar_nenhum():
    with (
        patch(
            "apps.acervo.services.abstracts.lookup_doi",
            return_value=LookupResultado(encontrado=False),
        ),
        patch(
            "apps.acervo.services.abstracts.abstract_por_doi", return_value=""
        ),
    ):
        texto, fonte = buscar_abstract("10.1/a")
    assert (texto, fonte) == ("", "")


# ---------------------------------------------------------------------------
# Comando — preenche, respeita salvaguardas, propaga ao Artigo
# ---------------------------------------------------------------------------


def _run(**opts):
    out = StringIO()
    with patch(
        "apps.anco.management.commands.backfill_resumos.buscar_abstract",
        return_value=(ABSTRACT_COMPLETO, "openalex"),
    ):
        call_command("backfill_resumos", projeto="piloto-anco-x", stdout=out, **opts)
    return out.getvalue()


@pytest.fixture
def projeto_slug(projeto):
    projeto.slug = "piloto-anco-x"
    projeto.save()
    return projeto


def test_preenche_truncado_e_propaga_ao_artigo(projeto_slug):
    it = _item(projeto_slug, resumo="Neither always rationally ...", ident="t1")
    _run()
    it.refresh_from_db()
    it.artigo.refresh_from_db()
    assert it.resumo == ABSTRACT_COMPLETO
    assert it.artigo.resumo == ABSTRACT_COMPLETO  # sincronizado


def test_preenche_vazio(projeto_slug):
    it = _item(projeto_slug, resumo="", ident="v1")
    _run()
    it.refresh_from_db()
    assert it.resumo == ABSTRACT_COMPLETO


def test_nao_toca_resumo_completo(projeto_slug):
    completo = "Um resumo já completo, longo e sem reticências no final, preservado."
    it = _item(projeto_slug, resumo=completo, ident="c1")
    _run()
    it.refresh_from_db()
    assert it.resumo == completo


def test_so_truncados_ignora_vazios(projeto_slug):
    vazio = _item(projeto_slug, resumo="", ident="sv1")
    trunc = _item(projeto_slug, resumo="cortado ...", ident="st1", doi="10.1/b")
    _run(so_truncados=True)
    vazio.refresh_from_db()
    trunc.refresh_from_db()
    assert vazio.resumo == ""
    assert trunc.resumo == ABSTRACT_COMPLETO


def test_dry_run_nao_grava(projeto_slug):
    it = _item(projeto_slug, resumo="cortado ...", ident="d1")
    _run(dry_run=True)
    it.refresh_from_db()
    assert it.resumo == "cortado ..."


def test_ignora_item_sem_doi(projeto_slug):
    it = _item(projeto_slug, resumo="cortado ...", ident="nd1", doi="", com_artigo=False)
    _run()
    it.refresh_from_db()
    assert it.resumo == "cortado ..."  # sem DOI, não é candidato


def test_nao_substitui_por_versao_mais_curta(projeto_slug):
    # Resumo truncado mais longo que o "completo" recuperado → mantém o atual.
    longo_truncado = "x" * (len(ABSTRACT_COMPLETO) + 10) + " ..."
    it = _item(projeto_slug, resumo=longo_truncado, ident="lc1")
    _run()
    it.refresh_from_db()
    assert it.resumo == longo_truncado  # sem ganho de tamanho, não troca
