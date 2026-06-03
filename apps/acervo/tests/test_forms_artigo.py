"""Testes do M4: IdentificadorLookupForm + ArtigoMetadadosForm."""

from __future__ import annotations

import pytest

from apps.acervo.forms import ArtigoMetadadosForm, IdentificadorLookupForm
from apps.vocabulario.models import TermoVocabulario, Vocabulario

# ---------------------------------------------------------------------------
# IdentificadorLookupForm
# ---------------------------------------------------------------------------


class TestIdentificadorLookupForm:
    def test_doi_canonico_detectado(self):
        f = IdentificadorLookupForm(data={"identificador": "10.1016/j.cogsys.2012.05.003"})
        assert f.is_valid()
        assert f.cleaned_data["identificador"] == {
            "tipo": "doi",
            "valor": "10.1016/j.cogsys.2012.05.003",
        }

    def test_doi_com_url_normaliza(self):
        f = IdentificadorLookupForm(
            data={"identificador": "https://doi.org/10.1016/x"}
        )
        assert f.is_valid()
        assert f.cleaned_data["identificador"] == {"tipo": "doi", "valor": "10.1016/x"}

    def test_isbn13_detectado(self):
        f = IdentificadorLookupForm(data={"identificador": "9780128038031"})
        assert f.is_valid()
        assert f.cleaned_data["identificador"] == {
            "tipo": "isbn",
            "valor": "9780128038031",
        }

    def test_isbn10_detectado(self):
        f = IdentificadorLookupForm(data={"identificador": "0521635039"})
        assert f.is_valid()
        assert f.cleaned_data["identificador"]["tipo"] == "isbn"

    def test_isbn_com_hifens_normaliza(self):
        f = IdentificadorLookupForm(data={"identificador": "978-0-12-803803-1"})
        assert f.is_valid()
        assert f.cleaned_data["identificador"] == {
            "tipo": "isbn",
            "valor": "9780128038031",
        }

    def test_url_doi_org_eh_doi_nao_url(self):
        # DOI tem prioridade sobre URL — `https://doi.org/...` é normalizado primeiro
        f = IdentificadorLookupForm(data={"identificador": "https://doi.org/10.1016/x"})
        assert f.is_valid()
        assert f.cleaned_data["identificador"]["tipo"] == "doi"

    def test_url_generica_eh_url(self):
        f = IdentificadorLookupForm(
            data={"identificador": "https://example.org/livro/123"}
        )
        assert f.is_valid()
        assert f.cleaned_data["identificador"] == {
            "tipo": "url",
            "valor": "https://example.org/livro/123",
        }

    def test_lixo_textual_eh_desconhecido(self):
        f = IdentificadorLookupForm(data={"identificador": "Não consta"})
        assert f.is_valid()
        assert f.cleaned_data["identificador"]["tipo"] == "desconhecido"

    def test_vazio_eh_vazio(self):
        f = IdentificadorLookupForm(data={"identificador": "  "})
        assert f.is_valid()
        assert f.cleaned_data["identificador"] == {"tipo": "vazio", "valor": ""}


# ---------------------------------------------------------------------------
# ArtigoMetadadosForm
# ---------------------------------------------------------------------------


@pytest.fixture
def base_consulta(db):
    vocab, _ = Vocabulario.objects.get_or_create(codigo="base", defaults={"nome": "Base"})
    termo, _ = TermoVocabulario.objects.get_or_create(
        vocabulario=vocab, nome="Web of Science", defaults={"ativo": True}
    )
    return termo


def _payload_minimo(base_consulta_id, **overrides):
    """Payload mínimo válido com link e base."""
    base = {
        "titulo": "Artigo de teste",
        "ano": "2024",
        "link_acesso": "https://example.org/artigo",
        "base_consulta": str(base_consulta_id),
        "tipo_publicacao": "artigo",
        "area": "Ciências Humanas",
    }
    base.update(overrides)
    return base


class TestArtigoMetadadosForm:
    def test_valido_com_doi(self, db, base_consulta):
        f = ArtigoMetadadosForm(
            data=_payload_minimo(base_consulta.pk, doi="10.1016/x")
        )
        assert f.is_valid(), f.errors
        assert f.cleaned_data["doi"] == "10.1016/x"

    def test_area_obrigatoria(self, db, base_consulta):
        f = ArtigoMetadadosForm(
            data=_payload_minimo(base_consulta.pk, doi="10.1016/x", area="")
        )
        assert not f.is_valid()
        assert "area" in f.errors

    def test_area_so_aceita_grande_area_valida(self, db, base_consulta):
        f = ArtigoMetadadosForm(
            data=_payload_minimo(base_consulta.pk, doi="10.1016/x", area="Psicologia")
        )
        assert not f.is_valid()
        assert "area" in f.errors

    def test_valido_com_isbn13(self, db, base_consulta):
        f = ArtigoMetadadosForm(
            data=_payload_minimo(
                base_consulta.pk,
                isbn="9780128038031",
                tipo_publicacao="livro",
            )
        )
        assert f.is_valid(), f.errors
        assert f.cleaned_data["isbn"] == "9780128038031"

    def test_valido_com_isbn10(self, db, base_consulta):
        f = ArtigoMetadadosForm(
            data=_payload_minimo(
                base_consulta.pk,
                isbn="0521635039",
                tipo_publicacao="livro",
            )
        )
        assert f.is_valid(), f.errors

    def test_isbn_com_hifens_normaliza(self, db, base_consulta):
        f = ArtigoMetadadosForm(
            data=_payload_minimo(
                base_consulta.pk,
                isbn="978-0-12-803803-1",
                tipo_publicacao="livro",
            )
        )
        assert f.is_valid(), f.errors
        assert f.cleaned_data["isbn"] == "9780128038031"

    def test_isbn_invalido_rejeitado(self, db, base_consulta):
        f = ArtigoMetadadosForm(
            data=_payload_minimo(base_consulta.pk, isbn="9780128038032")
        )
        assert not f.is_valid()
        assert "isbn" in f.errors

    def test_doi_em_formato_errado_rejeitado(self, db, base_consulta):
        f = ArtigoMetadadosForm(
            data=_payload_minimo(base_consulta.pk, doi="apenas-texto")
        )
        assert not f.is_valid()
        assert "doi" in f.errors

    def test_doi_com_prefixo_url_normalizado(self, db, base_consulta):
        f = ArtigoMetadadosForm(
            data=_payload_minimo(
                base_consulta.pk, doi="https://doi.org/10.1016/x"
            )
        )
        assert f.is_valid(), f.errors
        assert f.cleaned_data["doi"] == "10.1016/x"

    def test_valido_so_com_titulo_e_ano(self, db, base_consulta):
        """Cadastro manual sem DOI/ISBN — gera identificador_interno no save."""
        f = ArtigoMetadadosForm(data=_payload_minimo(base_consulta.pk))
        assert f.is_valid(), f.errors

    def test_invalido_sem_titulo(self, db, base_consulta):
        f = ArtigoMetadadosForm(
            data=_payload_minimo(base_consulta.pk, titulo="")
        )
        assert not f.is_valid()

    def test_invalido_sem_link(self, db, base_consulta):
        f = ArtigoMetadadosForm(
            data=_payload_minimo(base_consulta.pk, link_acesso="")
        )
        assert not f.is_valid()
        assert "link_acesso" in f.errors

    def test_invalido_sem_base(self, db, base_consulta):
        data = _payload_minimo(base_consulta.pk)
        data.pop("base_consulta")
        f = ArtigoMetadadosForm(data=data)
        assert not f.is_valid()
        assert "base_consulta" in f.errors

    def test_artigo_form_alias_para_metadados(self):
        """Alias temporário ArtigoForm == ArtigoMetadadosForm."""
        from apps.acervo.forms import ArtigoForm

        assert ArtigoForm is ArtigoMetadadosForm
