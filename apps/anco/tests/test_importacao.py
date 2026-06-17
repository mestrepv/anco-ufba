"""Import ANCO: tudo que entra vira corpus e é promovido; dedup funde origem."""

import pytest

from apps.anco.importacao import importar_para_fonte
from apps.anco.models import FonteImport, ItemCorpus, ProjetoANCO

pytestmark = pytest.mark.django_db


def _registros():
    return [
        {
            "titulo": "Jogo epistêmico em DBR",
            "autores": "Silva, A",
            "ano": 2022,
            "doi": "10.1/a",
            "resumo": "r",
            "palavras_chaves": "k",
            "titulo_periodico": "J",
            "idioma": "pt",
            "link": "",
            "tipo": "Artigo",
        },
        {"titulo": "Outro estudo", "ano": 2021, "doi": "10.1/b"},
        {"titulo": "", "doi": "10.1/c"},  # ignorado (sem título)
    ]


def test_import_cria_corpus_e_promove():
    proj = ProjetoANCO.objects.create(nome="P")
    fonte = FonteImport.objects.create(projeto=proj, outra_base="Scopus")
    res = importar_para_fonte(fonte, _registros())
    assert (res.total, res.novos, res.ignorados) == (3, 2, 1)
    itens = ItemCorpus.objects.filter(projeto=proj)
    assert itens.count() == 2
    assert all(i.artigo_id for i in itens)  # tudo promovido ao acervo
    fonte.refresh_from_db()
    assert fonte.n_novos == 2 and fonte.n_ignorados == 1


def test_import_dedup_funde_origem():
    proj = ProjetoANCO.objects.create(nome="P")
    f1 = FonteImport.objects.create(projeto=proj, outra_base="Scopus")
    f2 = FonteImport.objects.create(projeto=proj, outra_base="WoS")
    importar_para_fonte(f1, [{"titulo": "X", "doi": "10.1/x"}])
    res = importar_para_fonte(f2, [{"titulo": "X (dup)", "doi": "10.1/x"}])
    assert res.duplicados == 1 and res.novos == 0
    item = ItemCorpus.objects.get(projeto=proj)
    assert item.origem_fontes.count() == 2  # as duas fontes


def test_registrar_artigo_no_corpus_idempotente_e_legado():
    """Artigo individual (DOI/manual): entra no corpus 1x; legado é isento."""
    from apps.acervo.models import Artigo
    from apps.anco.importacao import registrar_artigo_no_corpus
    from django.contrib.auth import get_user_model

    User = get_user_model()
    proj = ProjetoANCO.objects.create(nome="Indiv")
    por = User.objects.create_user(username="u", email="u@u.edu", password="x")

    art = Artigo.objects.create(titulo="Avulso", ano=2024, doi="10.5/ind", eh_legado=False)
    it1 = registrar_artigo_no_corpus(proj, art, por)
    it2 = registrar_artigo_no_corpus(proj, art, por)  # idempotente
    assert it1.pk == it2.pk
    assert proj.itens.count() == 1
    assert it1.artigo_id == art.pk
    fonte = it1.origem_fontes.get()
    assert fonte.base_nome == "Artigos individuais"
    assert fonte.n_novos == 1  # não incrementa no 2º registro

    legado = Artigo.objects.create(titulo="Curado", ano=2010, doi="10.5/leg", eh_legado=True)
    assert registrar_artigo_no_corpus(proj, legado, por) is None  # legado isento
    assert proj.itens.count() == 1
