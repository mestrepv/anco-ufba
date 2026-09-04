"""
Diretorio publico da equipe: quem entra e quem fica de fora.

A definicao vive em `User.objects.equipe_publica()` e alimenta tanto o
diretorio `/equipe` quanto a contagem exibida na home — os dois nao podem
divergir.
"""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

User = get_user_model()
pytestmark = pytest.mark.django_db


def _pessoa(username, **extra):
    """Analista com perfil minimo preenchido — entra no diretorio."""
    campos = {
        "papel": User.Papel.ANALISTA,
        "nome_exibicao": f"Fulano {username}",
        "vinculo_institucional": "IFBA",
        "is_active": True,
    }
    campos.update(extra)
    return User.objects.create_user(
        username=username, email=f"{username}@u.edu.br", password="x", **campos
    )


class TestEquipePublica:
    def test_analista_com_perfil_completo_entra(self):
        u = _pessoa("ana")
        assert u in User.objects.equipe_publica()

    def test_curador_entra_como_analista(self):
        u = _pessoa("cur", papel=User.Papel.CURADOR)
        assert u in User.objects.equipe_publica()

    def test_conta_de_servico_fica_fora(self):
        u = _pessoa("admin", papel=User.Papel.CURADOR, eh_conta_servico=True)
        assert u not in User.objects.equipe_publica()

    def test_conta_do_legado_fica_fora(self):
        u = _pessoa("leg", eh_legado=True)
        assert u not in User.objects.equipe_publica()

    def test_leitor_fica_fora(self):
        u = _pessoa("leit", papel=User.Papel.LEITOR)
        assert u not in User.objects.equipe_publica()

    def test_inativo_fica_fora(self):
        u = _pessoa("ina", is_active=False)
        assert u not in User.objects.equipe_publica()

    def test_perfil_incompleto_fica_fora(self):
        sem_nome = _pessoa("sn", nome_exibicao="")
        sem_vinculo = _pessoa("sv", vinculo_institucional="")
        equipe = User.objects.equipe_publica()
        assert sem_nome not in equipe
        assert sem_vinculo not in equipe


class TestConsistenciaEntreHomeEDiretorio:
    def test_contagem_da_home_bate_com_o_diretorio(self, client):
        _pessoa("p1")
        _pessoa("p2")
        _pessoa("servico", eh_conta_servico=True)

        resp_home = client.get(reverse("home"))
        resp_equipe = client.get(reverse("pagina_equipe"))

        assert resp_home.context["analistas_count"] == 2
        assert len(resp_equipe.context["analistas"]) == 2
        assert resp_home.context["analistas_count"] == resp_equipe.context["total"]

    def test_conta_de_servico_nao_aparece_na_pagina(self, client):
        _pessoa("servico", nome_exibicao="Analista de Teste", eh_conta_servico=True)
        resp = client.get(reverse("pagina_equipe"))
        assert resp.status_code == 200
        assert "Analista de Teste" not in resp.content.decode()
