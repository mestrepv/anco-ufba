"""Testes unitarios das funcoes de normalizacao do migrate_legacy."""

import pytest

from apps.acervo.management.commands.migrate_legacy import (
    gerar_id_legado,
    normalizar_ano,
    normalizar_doi,
    normalizar_nome_analista,
    para_booleano,
    texto_limpo,
)

# ---- normalizar_ano ----


class TestNormalizarAno:
    def test_inteiro_valido_passa_inalterado(self):
        assert normalizar_ano(2020) == 2020

    def test_string_numerica_valida_vira_int(self):
        assert normalizar_ano("2020") == 2020

    def test_inteiro_fora_da_janela_vira_none(self):
        assert normalizar_ano(21) is None
        assert normalizar_ano(2921) is None
        assert normalizar_ano(218) is None

    def test_vazio_vira_none(self):
        assert normalizar_ano("") is None
        assert normalizar_ano(None) is None

    def test_string_nao_numerica_vira_none(self):
        assert normalizar_ano("dois mil") is None


# ---- normalizar_doi ----


class TestNormalizarDoi:
    def test_doi_canonico_passa_inalterado(self):
        assert normalizar_doi("10.1234/abc.456") == "10.1234/abc.456"

    def test_strip_prefixo_doi(self):
        assert normalizar_doi("DOI: 10.1234/abc") == "10.1234/abc"
        assert normalizar_doi("doi:10.1234/abc") == "10.1234/abc"
        assert normalizar_doi("DOI:  10.1234/abc") == "10.1234/abc"

    def test_extrai_de_url(self):
        assert normalizar_doi("https://doi.org/10.1234/abc") == "10.1234/abc"
        assert normalizar_doi("http://dx.doi.org/10.1234/abc.def") == "10.1234/abc.def"

    def test_remove_pontuacao_final(self):
        assert normalizar_doi("10.1234/abc.") == "10.1234/abc"
        assert normalizar_doi("10.1234/abc;") == "10.1234/abc"

    def test_issn_nao_e_doi(self):
        assert normalizar_doi("0138-9130") is None
        assert normalizar_doi("1234-567X") is None

    def test_vazio_e_placeholders(self):
        assert normalizar_doi("") is None
        assert normalizar_doi("-") is None
        assert normalizar_doi(None) is None
        assert normalizar_doi(123) is None  # tipo errado


# ---- gerar_id_legado ----


class TestGerarIdLegado:
    def test_e_deterministico(self):
        a = gerar_id_legado("Titulo X", 2020, "Periodico Y")
        b = gerar_id_legado("Titulo X", 2020, "Periodico Y")
        assert a == b

    def test_prefixo_legacy(self):
        assert gerar_id_legado("a", 2020, "b").startswith("legacy:")

    def test_diferentes_inputs_geram_ids_diferentes(self):
        a = gerar_id_legado("X", 2020, "Y")
        b = gerar_id_legado("Z", 2020, "Y")
        assert a != b

    def test_case_e_whitespace_irrelevantes(self):
        a = gerar_id_legado("Titulo", 2020, "Periodico")
        b = gerar_id_legado("  TITULO  ", 2020, "PERIODICO  ")
        assert a == b

    def test_aceita_ano_none(self):
        # ano None nao deve quebrar
        result = gerar_id_legado("X", None, "Y")
        assert result.startswith("legacy:")


# ---- para_booleano ----


class TestParaBooleano:
    @pytest.mark.parametrize("v", ["sim", "Sim", "SIM", "s", "S", "1", "x", "X", "yes", "Y"])
    def test_true_tokens(self, v):
        assert para_booleano(v) is True

    @pytest.mark.parametrize("v", ["nao", "não", "Não", "NÃO", "n", "N", "0", "no"])
    def test_false_tokens(self, v):
        assert para_booleano(v) is False

    def test_int_zero_e_um(self):
        assert para_booleano(0) is False
        assert para_booleano(1) is True

    def test_bool_passa_inalterado(self):
        assert para_booleano(True) is True
        assert para_booleano(False) is False

    def test_vazio_vira_none(self):
        assert para_booleano("") is None
        assert para_booleano(None) is None
        assert para_booleano("   ") is None

    def test_texto_longo_vira_none(self):
        assert para_booleano("contribui parcialmente") is None
        assert para_booleano("ver tabela 3") is None


# ---- texto_limpo ----


class TestTextoLimpo:
    def test_strip_simples(self):
        assert texto_limpo("  abc  ") == "abc"

    def test_placeholders_viram_vazio(self):
        assert texto_limpo("-") == ""
        assert texto_limpo("") == ""
        assert texto_limpo("   ") == ""
        assert texto_limpo(None) == ""

    def test_preserva_pontuacao(self):
        assert texto_limpo("Texto, com vírgula.") == "Texto, com vírgula."


# ---- normalizar_nome_analista ----


class TestNormalizarNomeAnalista:
    def test_title_case(self):
        assert normalizar_nome_analista("MARIA SILVA") == "Maria Silva"
        assert normalizar_nome_analista("maria silva") == "Maria Silva"
        assert normalizar_nome_analista("Maria SILVA") == "Maria Silva"

    def test_strip(self):
        assert normalizar_nome_analista("  Maria Silva  ") == "Maria Silva"

    def test_vazio(self):
        assert normalizar_nome_analista("") == ""
        assert normalizar_nome_analista(None) == ""
        assert normalizar_nome_analista("   ") == ""

    def test_nome_muito_longo_e_descartado(self):
        # Heuristica: descricao de artigo no campo errado
        descricao = (
            "Os autores fazem uma análise cognitiva da atuação transitória dos bolsistas " * 3
        )
        assert normalizar_nome_analista(descricao) == ""

    def test_nome_com_pontuacao_excessiva_e_descartado(self):
        # >2 pontos finais sugere texto livre, nao nome
        assert normalizar_nome_analista("Frase. Outra frase. Mais uma.") == ""

    def test_nome_normal_com_pontuacao_aceita(self):
        # Um Sr. ou Dr. eh ok
        assert normalizar_nome_analista("Dr. Jose Silva") == "Dr. Jose Silva"
