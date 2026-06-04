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


def _upload(client, base_termo, n_identificados, conteudo=RIS, **extra):
    arq = SimpleUploadedFile("scopus.ris", conteudo.encode("utf-8"))
    data = {
        "base_consulta": base_termo.pk, "formato": "", "arquivo": arq,
        "n_identificados": n_identificados, **extra,
    }
    return client.post(reverse("triagem_importar"), data=data)


def test_n_identificados_obrigatorio(client, analista, base_termo, settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)
    client.force_login(analista)
    arq = SimpleUploadedFile("s.ris", RIS.encode("utf-8"))
    resp = client.post(
        reverse("triagem_importar"),
        data={"base_consulta": base_termo.pk, "arquivo": arq},  # sem n_identificados
    )
    assert resp.status_code == 200  # re-renderiza com erro
    assert b"obrigat" in resp.content.lower() or b"required" in resp.content.lower()
    assert not Busca.objects.exists()


def test_upload_redireciona_e_guarda_campos(client, analista, base_termo, settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)
    client.force_login(analista)
    resp = _upload(client, base_termo, 1, string_busca="cog", filtros="2017-2025; inglês")
    assert resp.status_code == 302
    busca = Busca.objects.latest("pk")
    assert busca.n_identificados == 1
    assert busca.filtros == "2017-2025; inglês"
    resumo = client.get(resp.headers["Location"])
    assert resumo.status_code == 200
    assert b"lidos do arquivo" in resumo.content


def test_resumo_avisa_divergencia(client, analista, base_termo, settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)
    client.force_login(analista)
    # base reportou 466, mas o arquivo só tem 1 registro
    resp = _upload(client, base_termo, 466)
    resumo = client.get(resp.headers["Location"])
    assert b"Diverg" in resumo.content
    assert b"incompleto" in resumo.content
    assert b"466" in resumo.content


def test_resumo_confere_quando_bate(client, analista, base_termo, settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)
    client.force_login(analista)
    resp = _upload(client, base_termo, 1)  # arquivo tem 1, informado 1
    resumo = client.get(resp.headers["Location"])
    assert b"Confere" in resumo.content
