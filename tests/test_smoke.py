"""Testes de fumaca: garantem que o projeto Django esta saudavel."""

from io import StringIO

import pytest
from django.core.management import call_command
from django.db import connection
from django.test import Client


def test_django_check_passa() -> None:
    """`manage.py check` nao deve apontar issues."""
    out = StringIO()
    call_command("check", stdout=out)
    assert "no issues" in out.getvalue().lower()


@pytest.mark.django_db
def test_banco_de_dados_responde() -> None:
    """Conexao com Postgres do compose esta funcional."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        assert cursor.fetchone() == (1,)


@pytest.mark.django_db
def test_healthcheck_responde_ok() -> None:
    """Endpoint /healthz retorna 200 com 'ok'."""
    client = Client()
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.content == b"ok"
