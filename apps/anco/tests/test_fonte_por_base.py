"""Estatística do corpus POR BASE (não pela forma de inclusão).

Cobre o forward fix (a fonte do "Artigo individual" herda a base real do artigo)
e o backfill `corrigir_fonte_individual` que conserta os itens já existentes.
"""

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.urls import reverse

from apps.acervo.models import Artigo
from apps.anco.estatisticas import estatisticas_por_base
from apps.anco.importacao import registrar_artigo_no_corpus
from apps.anco.models import FonteImport, ItemCorpus, MembroANCO, ProjetoANCO
from apps.vocabulario.models import TermoVocabulario, Vocabulario

User = get_user_model()
pytestmark = pytest.mark.django_db


@pytest.fixture
def por(db):
    return User.objects.create_user(username="u", email="u@u.edu", password="x")


@pytest.fixture
def projeto(db):
    return ProjetoANCO.objects.create(nome="P")


def _base(nome):
    vocab, _ = Vocabulario.objects.get_or_create(codigo="base", defaults={"nome": "Base"})
    termo, _ = TermoVocabulario.objects.get_or_create(
        vocabulario=vocab, nome=nome, defaults={"ativo": True}
    )
    return termo


# --------------------------------------------------------------------------- #
# Forward fix
# --------------------------------------------------------------------------- #


def test_individual_herda_base_fk_do_artigo(projeto, por):
    redalyc = _base("Redalyc")
    art = Artigo.objects.create(titulo="X", ano=2024, doi="10.1/x", base_consulta=redalyc)

    item, criado = registrar_artigo_no_corpus(projeto, art, por)

    fonte = item.origem_fontes.get()
    assert fonte.base_consulta_id == redalyc.pk
    assert fonte.individual is True
    assert fonte.base_nome == "Redalyc"
    assert estatisticas_por_base(projeto) == [{"base": "Redalyc", "n": 1}]


def test_individual_herda_base_texto_livre(projeto, por):
    art = Artigo.objects.create(
        titulo="Y", ano=2024, doi="10.1/y", outra_base_consulta="PubMed"
    )

    item, _ = registrar_artigo_no_corpus(projeto, art, por)

    fonte = item.origem_fontes.get()
    assert fonte.base_consulta_id is None
    assert fonte.individual is True
    assert fonte.base_nome == "PubMed"


def test_individual_sem_base_cai_no_generico(projeto, por):
    art = Artigo.objects.create(titulo="Z", ano=2024, doi="10.1/z")

    item, _ = registrar_artigo_no_corpus(projeto, art, por)

    fonte = item.origem_fontes.get()
    assert fonte.individual is True
    assert fonte.base_nome == "Artigos individuais"


def test_duas_bases_diferentes_geram_duas_fontes(projeto, por):
    a1 = Artigo.objects.create(titulo="A", ano=2024, doi="10.1/a", base_consulta=_base("RIAnCo"))
    a2 = Artigo.objects.create(titulo="B", ano=2024, doi="10.1/b", base_consulta=_base("Redalyc"))

    registrar_artigo_no_corpus(projeto, a1, por)
    registrar_artigo_no_corpus(projeto, a2, por)

    stats = {s["base"]: s["n"] for s in estatisticas_por_base(projeto)}
    assert stats == {"RIAnCo": 1, "Redalyc": 1}
    assert FonteImport.objects.filter(projeto=projeto, individual=True).count() == 2


# --------------------------------------------------------------------------- #
# Backfill (dados legados no balde "Artigos individuais")
# --------------------------------------------------------------------------- #


def _estado_legado(projeto, por, art, ident="id-1"):
    """Recria o estado ANTIGO: item no balde genérico (individual=False)."""
    generica = FonteImport.objects.create(
        projeto=projeto, criado_por=por, outra_base="Artigos individuais"
    )
    item = ItemCorpus.objects.create(
        projeto=projeto, identificador=ident, titulo=art.titulo, artigo=art
    )
    item.origem_fontes.add(generica)
    return generica, item


def test_backfill_reatribui_por_base(projeto, por):
    redalyc = _base("Redalyc")
    art = Artigo.objects.create(titulo="Leg", ano=2020, doi="10.1/leg", base_consulta=redalyc)
    generica, item = _estado_legado(projeto, por, art)
    assert estatisticas_por_base(projeto) == [{"base": "Artigos individuais", "n": 1}]

    call_command("corrigir_fonte_individual", projeto=projeto.slug)

    item.refresh_from_db()
    assert [f.base_nome for f in item.origem_fontes.all()] == ["Redalyc"]
    assert not FonteImport.objects.filter(pk=generica.pk).exists()  # balde vazio removido
    assert estatisticas_por_base(projeto) == [{"base": "Redalyc", "n": 1}]


def test_backfill_dry_run_nao_altera(projeto, por):
    art = Artigo.objects.create(titulo="Leg", ano=2020, doi="10.1/leg", base_consulta=_base("RIAnCo"))
    generica, item = _estado_legado(projeto, por, art)

    call_command("corrigir_fonte_individual", projeto=projeto.slug, dry_run=True)

    assert FonteImport.objects.filter(pk=generica.pk).exists()
    item.refresh_from_db()
    assert [f.base_nome for f in item.origem_fontes.all()] == ["Artigos individuais"]


def test_backfill_idempotente(projeto, por):
    art = Artigo.objects.create(titulo="Leg", ano=2020, doi="10.1/leg", base_consulta=_base("Redalyc"))
    _estado_legado(projeto, por, art)

    call_command("corrigir_fonte_individual", projeto=projeto.slug)
    call_command("corrigir_fonte_individual", projeto=projeto.slug)  # 2ª vez: nada a fazer

    assert estatisticas_por_base(projeto) == [{"base": "Redalyc", "n": 1}]


def test_backfill_sem_base_mantem_no_generico(projeto, por):
    art = Artigo.objects.create(titulo="SemBase", ano=2020, doi="10.1/sb")  # sem base
    generica, item = _estado_legado(projeto, por, art)

    call_command("corrigir_fonte_individual", projeto=projeto.slug)

    item.refresh_from_db()
    assert [f.base_nome for f in item.origem_fontes.all()] == ["Artigos individuais"]
    generica.refresh_from_db()
    assert generica.individual is True  # balde mantido, agora marcado


def test_corpus_dropdown_agrupa_por_base_e_filtra(client, projeto, por):
    """O filtro de procedência lista uma opção por BASE (não por importação/data)."""
    redalyc = _base("Redalyc")
    por.pode_anco = True
    por.save(update_fields=["pode_anco"])
    MembroANCO.objects.create(projeto=projeto, usuario=por, papel=MembroANCO.Papel.ANALISTA)
    # Duas importações Redalyc distintas + uma Scopus.
    f1 = FonteImport.objects.create(projeto=projeto, criado_por=por, base_consulta=redalyc)
    f2 = FonteImport.objects.create(projeto=projeto, criado_por=por, base_consulta=redalyc)
    f3 = FonteImport.objects.create(projeto=projeto, criado_por=por, base_consulta=_base("Scopus"))
    for i, f in enumerate([f1, f1, f2, f3]):  # 3 Redalyc, 1 Scopus
        a = Artigo.objects.create(titulo=f"A{i}", ano=2024, doi=f"10.1/{i}")
        it = ItemCorpus.objects.create(
            projeto=projeto, identificador=f"id{i}", titulo=a.titulo, artigo=a
        )
        it.origem_fontes.add(f)
    client.force_login(por)

    resp = client.get(reverse("anco_corpus", args=[projeto.slug]))
    assert resp.status_code == 200
    # Redalyc aparece UMA vez (3), não duas (por data); Scopus (1).
    assert resp.context["bases"] == [{"nome": "Redalyc", "n": 3}, {"nome": "Scopus", "n": 1}]

    filtrado = client.get(reverse("anco_corpus", args=[projeto.slug]) + "?fonte=Redalyc")
    assert len(filtrado.context["itens"]) == 3


def test_corpus_filtra_por_importacao_especifica(client, projeto, por):
    """`?import=<pk>` mostra só os itens daquela importação (não da base inteira)."""
    redalyc = _base("Redalyc")
    por.pode_anco = True
    por.save(update_fields=["pode_anco"])
    MembroANCO.objects.create(projeto=projeto, usuario=por, papel=MembroANCO.Papel.ANALISTA)
    f1 = FonteImport.objects.create(projeto=projeto, criado_por=por, base_consulta=redalyc)
    f2 = FonteImport.objects.create(projeto=projeto, criado_por=por, base_consulta=redalyc)
    for i, f in enumerate([f1, f1, f2]):  # 2 na f1, 1 na f2 (mesma base)
        a = Artigo.objects.create(titulo=f"T{i}", ano=2024, doi=f"10.2/{i}")
        it = ItemCorpus.objects.create(
            projeto=projeto, identificador=f"im{i}", titulo=a.titulo, artigo=a
        )
        it.origem_fontes.add(f)
    client.force_login(por)

    resp = client.get(reverse("anco_corpus", args=[projeto.slug]) + f"?import={f1.pk}")

    assert resp.status_code == 200
    assert resp.context["import_fonte"].pk == f1.pk
    assert len(resp.context["itens"]) == 2  # só os de f1, não o de f2


def test_backfill_nao_duplica_base_ja_presente(projeto, por):
    """Item já numa fonte (lote) da mesma base + no balde: só sai do balde."""
    redalyc = _base("Redalyc")
    art = Artigo.objects.create(titulo="Dup", ano=2020, doi="10.1/dup", base_consulta=redalyc)
    lote = FonteImport.objects.create(projeto=projeto, criado_por=por, base_consulta=redalyc)
    generica, item = _estado_legado(projeto, por, art)
    item.origem_fontes.add(lote)  # também veio da Redalyc em lote

    call_command("corrigir_fonte_individual", projeto=projeto.slug)

    item.refresh_from_db()
    assert [f.pk for f in item.origem_fontes.all()] == [lote.pk]  # só o lote, sem duplicar
    assert estatisticas_por_base(projeto) == [{"base": "Redalyc", "n": 1}]  # contado uma vez
