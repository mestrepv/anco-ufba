"""Fase 10.1 — resumo de deduplicação por busca."""

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.acervo.models import Artigo
from apps.triagem.importacao import importar_para_busca, parse_ris
from apps.triagem.models import Busca, ProtocoloTriagem
from apps.vocabulario.models import TermoVocabulario, Vocabulario

User = get_user_model()
pytestmark = pytest.mark.django_db

RIS = """TY  - JOUR
TI  - Estudo sobre cognição
AU  - Silva, J.
PY  - 2020
DO  - 10.1/abc
ER  -
"""


@pytest.fixture
def protocolo(db):
    return ProtocoloTriagem.ativo()


@pytest.fixture
def base_termo(db):
    v, _ = Vocabulario.objects.get_or_create(codigo="base", defaults={"nome": "Base"})
    return TermoVocabulario.objects.create(vocabulario=v, nome="Scopus")


@pytest.fixture
def analista(db):
    return User.objects.create_user(
        username="ana", email="a@u.edu", password="x", papel=User.Papel.ANALISTA
    )


def test_menu_base_sem_prefixo(base_termo):
    from apps.triagem.forms import ImportarBuscaForm

    labels = [str(label) for _, label in ImportarBuscaForm().fields["base_consulta"].choices]
    assert "Scopus" in labels
    assert not any("base:" in label for label in labels)


def test_import_persiste_contagens_na_busca(protocolo, base_termo):
    b = Busca.objects.create(protocolo=protocolo, base_consulta=base_termo)
    importar_para_busca(b, parse_ris(RIS))
    b.refresh_from_db()
    assert b.n_lidos == 1
    assert b.n_novos == 1
    assert b.n_ja_no_acervo == 0
    assert b.importado_em is not None


def test_ja_no_acervo_contado(protocolo, base_termo):
    Artigo.objects.create(doi="10.1/abc", titulo="x", ano=2020, base_consulta=base_termo)
    b = Busca.objects.create(protocolo=protocolo, base_consulta=base_termo)
    importar_para_busca(b, parse_ris(RIS))
    b.refresh_from_db()
    assert b.n_ja_no_acervo == 1 and b.n_novos == 0


def test_upload_redireciona_para_resumo(client, analista, base_termo, settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)
    client.force_login(analista)
    arq = SimpleUploadedFile("scopus.ris", RIS.encode("utf-8"))
    resp = client.post(
        reverse("triagem_importar"),
        data={"base_consulta": base_termo.pk, "formato": "", "arquivo": arq},
    )
    assert resp.status_code == 302
    busca = Busca.objects.latest("pk")
    assert resp.headers["Location"] == reverse("triagem_busca_resumo", args=[busca.pk])

    resumo = client.get(resp.headers["Location"])
    assert resumo.status_code == 200
    assert b"Importa" in resumo.content
    assert b"novos" in resumo.content
