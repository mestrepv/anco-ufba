"""normalizar_url + comando corrigir_links — links de esquema embutido."""

from io import StringIO

import pytest
from django.core.management import call_command

from apps.acervo.models import Artigo
from apps.anco.models import ItemCorpus, ProjetoANCO
from apps.anco.parsers import normalizar_url

pytestmark = pytest.mark.django_db


class TestNormalizarUrl:
    def test_doi_duplicado(self):
        assert (
            normalizar_url("https://doi.org/https://doi.org/10.1177/x")
            == "https://doi.org/10.1177/x"
        )

    def test_doi_org_colado_em_url_de_editora(self):
        assert (
            normalizar_url("https://doi.org/https://journals.sagepub.com/doi/abs/10.3233/y")
            == "https://journals.sagepub.com/doi/abs/10.3233/y"
        )

    def test_url_limpa_fica_intacta(self):
        assert normalizar_url("https://doi.org/10.1177/x") == "https://doi.org/10.1177/x"
        assert normalizar_url("https://example.com/a") == "https://example.com/a"

    def test_idempotente_em_triplo(self):
        assert (
            normalizar_url("https://doi.org/https://doi.org/https://doi.org/10.1/x")
            == "https://doi.org/10.1/x"
        )

    def test_vazio_e_none(self):
        assert normalizar_url("") == ""
        assert normalizar_url(None) == ""


class TestComandoCorrigirLinks:
    def _projeto(self):
        return ProjetoANCO.objects.create(nome="Piloto", slug="piloto-x", pergunta_pesquisa="Q?")

    def _item(self, projeto, link, ident, doi="10.1/a", com_artigo=True):
        artigo = None
        if com_artigo:
            artigo = Artigo.objects.create(titulo="Obra", ano=2023, doi=doi, link_acesso=link)
        return ItemCorpus.objects.create(
            projeto=projeto, titulo="Obra", identificador=ident, doi=doi, link=link, artigo=artigo
        )

    def _run(self, **opts):
        out = StringIO()
        call_command("corrigir_links", projeto="piloto-x", stdout=out, **opts)
        return out.getvalue()

    def test_corrige_item_e_propaga_ao_artigo(self):
        p = self._projeto()
        it = self._item(p, "https://doi.org/https://doi.org/10.1/a", "k1")
        self._run()
        it.refresh_from_db()
        it.artigo.refresh_from_db()
        assert it.link == "https://doi.org/10.1/a"
        assert it.artigo.link_acesso == "https://doi.org/10.1/a"

    def test_nao_toca_link_ja_limpo(self):
        p = self._projeto()
        it = self._item(p, "https://doi.org/10.1/a", "k2")
        saida = self._run()
        it.refresh_from_db()
        assert it.link == "https://doi.org/10.1/a"
        assert "0 link(s) foram corrigido(s)" in saida

    def test_dry_run_nao_grava(self):
        p = self._projeto()
        it = self._item(p, "https://doi.org/https://doi.org/10.1/a", "k3")
        self._run(dry_run=True)
        it.refresh_from_db()
        assert it.link == "https://doi.org/https://doi.org/10.1/a"

    def test_idempotente(self):
        p = self._projeto()
        self._item(p, "https://doi.org/https://doi.org/10.1/a", "k4")
        self._run()
        saida2 = self._run()  # segunda passada não acha mais nada
        assert "0 item(ns) com link de esquema embutido" in saida2
