"""Ações em massa do UserAdmin (promover papel / admin / revisor)."""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

User = get_user_model()
pytestmark = pytest.mark.django_db


@pytest.fixture
def admin(db):
    return User.objects.create_superuser(username="adm", email="adm@x.org", password="x")


@pytest.fixture
def alvo(db):
    return User.objects.create_user(
        username="u", email="u@x.org", password="x", papel=User.Papel.ANALISTA
    )


def _run(client, acao, alvo):
    url = reverse("admin:core_user_changelist")
    return client.post(url, {"action": acao, "_selected_action": [alvo.pk]})


def test_promover_curador(client, admin, alvo):
    client.force_login(admin)
    _run(client, "promover_curador", alvo)
    alvo.refresh_from_db()
    assert alvo.papel == User.Papel.CURADOR


def test_conceder_admin(client, admin, alvo):
    client.force_login(admin)
    assert alvo.is_staff is False
    _run(client, "conceder_admin", alvo)
    alvo.refresh_from_db()
    assert alvo.is_staff is True


def test_aprovar_revisor(client, admin, alvo):
    client.force_login(admin)
    _run(client, "aprovar_revisor", alvo)
    alvo.refresh_from_db()
    assert alvo.revisor_aprovado is True


def test_revogar_admin_nao_afeta_o_proprio(client, admin):
    client.force_login(admin)
    _run(client, "revogar_admin", admin)  # tenta revogar o próprio
    admin.refresh_from_db()
    assert admin.is_staff is True  # protegido
