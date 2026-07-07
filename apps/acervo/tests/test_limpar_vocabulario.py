"""Limpeza segura dos vocabulários ANCO: desativa só redundância inequívoca."""

import pytest
from django.core.management import call_command

from apps.acervo.models import Analise, Artigo
from apps.vocabulario.models import TermoVocabulario, Vocabulario

pytestmark = pytest.mark.django_db


@pytest.fixture
def vocab_epi(db):
    return Vocabulario.objects.create(codigo="epistemologia", nome="Epistemologia")


def _t(v, nome, ativo=True):
    return TermoVocabulario.objects.create(vocabulario=v, nome=nome, ativo=ativo)


def test_desativa_glosa_redundante(vocab_epi, tmp_path):
    limpo = _t(vocab_epi, "Construtivista")
    glosado = _t(vocab_epi, "Construtivista (Teoria dos Obstáculos)")
    call_command("limpar_vocabulario_anco", "--apply", "--csv-dir", str(tmp_path))
    limpo.refresh_from_db()
    glosado.refresh_from_db()
    assert limpo.ativo is True
    assert glosado.ativo is False  # redundante com o termo limpo


def test_desativa_duplicata_caixa(vocab_epi, tmp_path):
    a = _t(vocab_epi, "Investigação Empírica")
    b = _t(vocab_epi, "Investigação empírica")
    call_command("limpar_vocabulario_anco", "--apply", "--csv-dir", str(tmp_path))
    a.refresh_from_db()
    b.refresh_from_db()
    assert a.ativo != b.ativo  # uma fica, a outra é desativada
    assert a.ativo or b.ativo


def test_atomiza_compostos(vocab_epi, tmp_path):
    # '/' e ';' eram limitação do Forms — aqui viram termos atômicos.
    comp = _t(vocab_epi, "Aplicada/Computacional")
    lista = _t(vocab_epi, "ACT-R; Psicologia Cognitiva")
    call_command("limpar_vocabulario_anco", "--apply", "--csv-dir", str(tmp_path))
    comp.refresh_from_db()
    lista.refresh_from_db()
    # Os compostos são DESATIVADOS (somem do picker)…
    assert comp.ativo is False
    assert lista.ativo is False
    # …e os átomos passam a existir ATIVOS para seleção individual.
    def _ativo(nome):
        return TermoVocabulario.objects.filter(
            vocabulario=vocab_epi, nome=nome, ativo=True
        ).exists()
    assert _ativo("Aplicada") and _ativo("Computacional")
    assert _ativo("ACT-R") and _ativo("Psicologia Cognitiva")


def test_glosa_com_ponto_e_virgula_nao_quebra(vocab_epi, tmp_path):
    # Glosa com ';' dentro NÃO deve gerar átomo quebrado (glosa sai antes do split).
    _t(vocab_epi, "Construtivista (Conhecimento ativo; Obstáculos)")
    call_command("limpar_vocabulario_anco", "--apply", "--csv-dir", str(tmp_path))
    assert TermoVocabulario.objects.filter(
        vocabulario=vocab_epi, nome="Construtivista", ativo=True
    ).exists()
    # Não criou "Construtivista (Conhecimento ativo" nem "Obstáculos".
    assert not TermoVocabulario.objects.filter(
        vocabulario=vocab_epi, nome__startswith="Construtivista ("
    ).filter(ativo=True).exists()


def test_nao_toca_analises(vocab_epi, tmp_path, django_user_model):
    u = django_user_model.objects.create_user(username="a", email="a@u.edu", password="x")
    art = Artigo.objects.create(titulo="T", ano=2020)
    ana = Analise.objects.create(artigo=art, analista=u, status=Analise.Status.LEGADO)
    _t(vocab_epi, "Construtivista")
    glosado = _t(vocab_epi, "Construtivista (X)")
    ana.epistemologia.set([glosado])  # legado referencia o glosado
    call_command("limpar_vocabulario_anco", "--apply", "--csv-dir", str(tmp_path))
    # A análise (legado) NÃO é alterada: continua referenciando o termo.
    assert list(ana.epistemologia.all()) == [glosado]
