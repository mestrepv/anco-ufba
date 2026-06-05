"""Fase 9.2 — parsers (RIS/BibTeX/CSV), dedup e isenção do legado."""

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.acervo.models import Artigo
from apps.triagem.importacao import (
    importar_para_busca,
    parse_bibtex,
    parse_csv,
    parse_ris,
)
from apps.triagem.models import Busca, ProtocoloTriagem, RegistroTriagem
from apps.vocabulario.models import TermoVocabulario, Vocabulario

from .conftest import membro, turl

User = get_user_model()
pytestmark = pytest.mark.django_db

RIS = """TY  - JOUR
TI  - Cognitive analysis in science education
AU  - Silva, J.
AU  - Souza, M.
PY  - 2020
DO  - 10.1000/abc123
AB  - A study about cognition.
KW  - cognition
KW  - education
JO  - Journal of Cognition
UR  - https://example.org/abc
LA  - eng
ER  -
"""

BIBTEX = """@article{silva2020,
  title = {Cognitive analysis in science education},
  author = {Silva, J. and Souza, M.},
  year = {2020},
  doi = {10.1000/abc123},
  abstract = {A study about cognition.},
  keywords = {cognition, education},
  journal = {Journal of Cognition},
  url = {https://example.org/abc},
  language = {english}
}
"""

CSV = (
    "titulo,autores,ano,doi,resumo,periodico,palavras-chave,idioma,link\n"
    "Cognitive analysis in science education,Silva; Souza,2020,10.1000/abc123,"
    "A study,Journal of Cognition,cognition; education,en,https://example.org/abc\n"
)


@pytest.fixture
def protocolo(db):
    return ProtocoloTriagem.ativo()


@pytest.fixture
def base_termo(db):
    v, _ = Vocabulario.objects.get_or_create(codigo="base", defaults={"nome": "Base"})
    return TermoVocabulario.objects.create(vocabulario=v, nome="Scopus")


# ---- parsers ---------------------------------------------------------------

def test_parse_extrai_tipo():
    assert parse_ris(RIS)[0]["tipo"] == "Artigo"  # TY - JOUR
    assert parse_bibtex(BIBTEX)[0]["tipo"] == "Artigo"  # @article


def test_import_grava_tipo(protocolo, base_termo):
    b = Busca.objects.create(protocolo=protocolo, base_consulta=base_termo)
    importar_para_busca(b, parse_ris(RIS))
    reg = RegistroTriagem.objects.get(protocolo=protocolo, doi="10.1000/abc123")
    assert reg.tipo == "Artigo"


def test_parse_ris_mapeia_campos():
    (r,) = parse_ris(RIS)
    assert r["titulo"] == "Cognitive analysis in science education"
    assert "Silva" in r["autores"] and "Souza" in r["autores"]
    assert r["ano"] == 2020
    assert r["doi"] == "10.1000/abc123"
    assert "cognition" in r["palavras_chaves"]
    assert r["titulo_periodico"] == "Journal of Cognition"
    assert r["link"] == "https://example.org/abc"


def test_parse_bibtex_mapeia_campos():
    (r,) = parse_bibtex(BIBTEX)
    assert r["titulo"] == "Cognitive analysis in science education"
    assert "; " in r["autores"]  # "and" virou "; "
    assert r["ano"] == 2020
    assert r["doi"] == "10.1000/abc123"
    assert r["titulo_periodico"] == "Journal of Cognition"


def test_parse_csv_mapeia_campos():
    (r,) = parse_csv(CSV)
    assert r["titulo"] == "Cognitive analysis in science education"
    assert r["ano"] == 2020
    assert r["doi"] == "10.1000/abc123"
    assert r["titulo_periodico"] == "Journal of Cognition"


# ---- dedup -----------------------------------------------------------------

def test_dedup_mescla_mesma_referencia_em_buscas_distintas(protocolo, base_termo):
    b1 = Busca.objects.create(protocolo=protocolo, base_consulta=base_termo)
    b2 = Busca.objects.create(protocolo=protocolo, outra_base="Outra")

    r1 = importar_para_busca(b1, parse_ris(RIS))
    assert r1.criados == 1 and r1.duplicados == 0

    r2 = importar_para_busca(b2, parse_bibtex(BIBTEX))  # mesmo DOI
    assert r2.criados == 0 and r2.duplicados == 1

    reg = RegistroTriagem.objects.get(protocolo=protocolo, doi="10.1000/abc123")
    assert set(reg.origem_buscas.all()) == {b1, b2}  # mesclou as duas origens


def test_reimportar_mesmo_arquivo_e_idempotente(protocolo, base_termo):
    b = Busca.objects.create(protocolo=protocolo, base_consulta=base_termo)
    importar_para_busca(b, parse_ris(RIS))
    antes = RegistroTriagem.objects.count()
    r2 = importar_para_busca(b, parse_ris(RIS))
    assert r2.criados == 0 and r2.duplicados == 1
    assert RegistroTriagem.objects.count() == antes


def test_registro_sem_titulo_e_ignorado(protocolo, base_termo):
    b = Busca.objects.create(protocolo=protocolo, base_consulta=base_termo)
    res = importar_para_busca(b, [{"titulo": "", "doi": "10.1/x"}])
    assert res.ignorados == 1 and res.criados == 0


# ---- isenção do legado -----------------------------------------------------

def test_candidato_ja_no_acervo_nao_vira_novo(protocolo, base_termo):
    artigo = Artigo.objects.create(
        doi="10.1000/abc123", titulo="X", ano=2020, base_consulta=base_termo,
        eh_legado=True,
    )
    b = Busca.objects.create(protocolo=protocolo, base_consulta=base_termo)
    res = importar_para_busca(b, parse_ris(RIS))
    assert res.ja_no_acervo == 1 and res.criados == 0
    reg = RegistroTriagem.objects.get(protocolo=protocolo, doi="10.1000/abc123")
    assert reg.ja_no_acervo is True
    assert reg.artigo_id == artigo.pk


# ---- upload view -----------------------------------------------------------

@pytest.fixture
def analista(db):
    return membro(User.objects.create_user(
        username="ana", email="a@u.edu.br", password="x", papel=User.Papel.ANALISTA
    ))


@pytest.fixture
def leitor(db):
    return User.objects.create_user(
        username="leit", email="l@u.edu.br", password="x", papel=User.Papel.LEITOR
    )


def test_leitor_nao_importa(client, leitor):
    client.force_login(leitor)
    assert client.get(turl("triagem_importar")).status_code == 403


def test_upload_ris_cria_registro(client, analista, base_termo, settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)
    client.force_login(analista)
    arquivo = SimpleUploadedFile("scopus.ris", RIS.encode("utf-8"), content_type="text/plain")
    resp = client.post(
        turl("triagem_importar"),
        data={"base_consulta": base_termo.pk, "outra_base": "", "formato": "",
              "string_busca": "cog", "n_identificados": 1, "arquivo": arquivo},
    )
    assert resp.status_code == 302
    busca = Busca.objects.filter(base_consulta=base_termo).latest("pk")
    assert resp.headers["Location"] == turl("triagem_busca_resumo", args=[busca.pk])
    assert RegistroTriagem.objects.filter(doi="10.1000/abc123").exists()
