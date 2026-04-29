"""Testes da resolucao de termos canonicos via sinonimos."""

import pytest

from apps.vocabulario.models import TermoVocabulario, Vocabulario


@pytest.fixture
def vocab_e_termos(db):
    voc = Vocabulario.objects.create(codigo="epistemologia", nome="Epistemologia")
    empirismo = TermoVocabulario.objects.create(
        vocabulario=voc,
        nome="Empirismo",
        sinonimos=["empirismo", "Empírica", "empirista"],
    )
    construtivismo = TermoVocabulario.objects.create(
        vocabulario=voc,
        nome="Construtivismo",
        sinonimos=["Construtivista"],
    )
    return voc, empirismo, construtivismo


class TestBuscarCanonico:
    def test_match_por_nome_canonico_exato(self, vocab_e_termos):
        _, empirismo, _ = vocab_e_termos
        assert TermoVocabulario.buscar_canonico("epistemologia", "Empirismo") == empirismo

    def test_match_por_nome_canonico_case_insensitive(self, vocab_e_termos):
        _, empirismo, _ = vocab_e_termos
        assert TermoVocabulario.buscar_canonico("epistemologia", "EMPIRISMO") == empirismo
        assert TermoVocabulario.buscar_canonico("epistemologia", "empirismo") == empirismo

    def test_match_por_sinonimo(self, vocab_e_termos):
        _, empirismo, _ = vocab_e_termos
        assert TermoVocabulario.buscar_canonico("epistemologia", "Empírica") == empirismo
        assert TermoVocabulario.buscar_canonico("epistemologia", "empirista") == empirismo

    def test_match_sinonimo_case_insensitive(self, vocab_e_termos):
        _, empirismo, _ = vocab_e_termos
        assert TermoVocabulario.buscar_canonico("epistemologia", "EMPÍRICA") == empirismo

    def test_termo_inexistente_retorna_none(self, vocab_e_termos):
        assert TermoVocabulario.buscar_canonico("epistemologia", "Pragmatismo") is None

    def test_vazio_retorna_none(self, vocab_e_termos):
        assert TermoVocabulario.buscar_canonico("epistemologia", "") is None
        assert TermoVocabulario.buscar_canonico("epistemologia", "   ") is None

    def test_vocabulario_inexistente_retorna_none(self, db):
        assert TermoVocabulario.buscar_canonico("inexistente", "qualquer") is None

    def test_nao_cruza_vocabularios_diferentes(self, vocab_e_termos):
        # cria termo em outro vocab com mesmo nome
        outro = Vocabulario.objects.create(codigo="teoria", nome="Teoria")
        TermoVocabulario.objects.create(vocabulario=outro, nome="Empirismo")
        # busca em "epistemologia" ainda devolve o de epistemologia
        _, empirismo, _ = vocab_e_termos
        assert TermoVocabulario.buscar_canonico("epistemologia", "Empirismo") == empirismo
