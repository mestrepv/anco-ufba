"""Facetação da Epistemologia: paradigma × método × disciplina, reversível."""

import pytest
from django.core.management import call_command

from apps.acervo.forms import AnaliseEstruturaForm
from apps.acervo.models import Analise, Artigo
from apps.vocabulario.models import TermoVocabulario, Vocabulario

pytestmark = pytest.mark.django_db


@pytest.fixture
def vocab(db):
    return Vocabulario.objects.create(codigo="epistemologia", nome="Epistemologia")


def _t(vocab, nome):
    return TermoVocabulario.objects.create(vocabulario=vocab, nome=nome, ativo=True)


def test_classifica_facetas(vocab):
    para = _t(vocab, "Empirismo")
    meto = _t(vocab, "Qualitativa")
    disc = _t(vocab, "Linguística Cognitiva")
    apl = _t(vocab, "Usabilidade")
    lixo = _t(vocab, "[Tópico não claro]")
    call_command("facetar_epistemologia", "--apply")
    for t in (para, meto, disc, apl, lixo):
        t.refresh_from_db()
    assert para.grupo == "paradigma"
    assert meto.grupo == "metodologia"
    assert disc.grupo == "disciplina"
    assert apl.grupo == "aplicacao"
    assert lixo.grupo == "lixo"


def test_desfazer_limpa_grupo(vocab):
    t = _t(vocab, "Empirismo")
    call_command("facetar_epistemologia", "--apply")
    t.refresh_from_db()
    assert t.grupo == "paradigma"
    call_command("facetar_epistemologia", "--desfazer")
    t.refresh_from_db()
    assert t.grupo == ""  # reversível


def test_picker_so_paradigma(vocab, django_user_model):
    para = _t(vocab, "Construtivista")
    meto = _t(vocab, "Experimental")
    call_command("facetar_epistemologia", "--apply")
    form = AnaliseEstruturaForm()
    ids = set(form.fields["epistemologia"].queryset.values_list("pk", flat=True))
    assert para.pk in ids
    assert meto.pk not in ids  # método sai do picker de epistemologia


def test_picker_preserva_selecionado_mesmo_fora_do_grupo(vocab, django_user_model):
    meto = _t(vocab, "Etnografia")  # método
    call_command("facetar_epistemologia", "--apply")
    u = django_user_model.objects.create_user(username="a", email="a@u.edu", password="x")
    art = Artigo.objects.create(titulo="T", ano=2020)
    ana = Analise.objects.create(artigo=art, analista=u, status=Analise.Status.RASCUNHO)
    ana.epistemologia.set([meto])  # análise antiga tinha o método em epistemologia
    form = AnaliseEstruturaForm(instance=ana)
    ids = set(form.fields["epistemologia"].queryset.values_list("pk", flat=True))
    assert meto.pk in ids  # não perde o valor já selecionado
