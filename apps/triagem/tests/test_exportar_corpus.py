"""Export do corpus em CSV (formato ASReview)."""

import csv

import pytest
from django.core.management import call_command

from apps.triagem.models import ProtocoloTriagem, RegistroTriagem

pytestmark = pytest.mark.django_db
_S = RegistroTriagem.Status


def test_exportar_corpus_csv(tmp_path):
    p = ProtocoloTriagem.objects.create(nome="P", slug="p-exp")
    RegistroTriagem.objects.create(
        protocolo=p, titulo="Inc", identificador="d:1", resumo="r1", status=_S.INCLUIDO
    )
    RegistroTriagem.objects.create(
        protocolo=p, titulo="Exc", identificador="d:2", status=_S.EXCLUIDO
    )
    RegistroTriagem.objects.create(
        protocolo=p, titulo="Ident", identificador="d:3", status=_S.IDENTIFICADO
    )
    RegistroTriagem.objects.create(
        protocolo=p, titulo="Dup", identificador="d:4", status=_S.DUPLICADO
    )

    arquivo = tmp_path / "corpus.csv"
    call_command("exportar_corpus", "p-exp", saida=str(arquivo))
    rows = list(csv.DictReader(arquivo.open(encoding="utf-8")))

    por_titulo = {r["title"]: r for r in rows}
    assert len(rows) == 3  # duplicata omitida
    assert "Dup" not in por_titulo
    assert por_titulo["Inc"]["label_included"] == "1"
    assert por_titulo["Exc"]["label_included"] == "0"
    assert por_titulo["Ident"]["label_included"] == ""
    assert por_titulo["Inc"]["abstract"] == "r1"  # colunas ASReview presentes
