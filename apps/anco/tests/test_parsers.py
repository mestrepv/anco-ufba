"""Parsers de importação do ANCO — foco em BibTeX (.bib) e PubMed MEDLINE (.nbib)."""

from apps.anco.parsers import (
    analisar_arquivo,
    detectar_formato,
    detectar_formato_conteudo,
    parse_medline,
)

MEDLINE = """PMID- 12345678
OWN - NLM
TI  - Cognitive analysis of decision making in clinical
      practice: a study.
AB  - This study examines cognitive processes in
      clinical decision making.
FAU - Smith, John A
AU  - Smith JA
FAU - Doe, Jane
AU  - Doe J
DP  - 2023 Jun
TA  - J Med Educ
JT  - Journal of Medical Education
LA  - eng
PT  - Journal Article
OT  - cognition
OT  - decision making
AID - 10.1000/example123 [doi]

PMID- 87654321
TI  - Second article title.
FAU - Brown, Bob
DP  - 2021
JT  - Another Journal
LID - 10.2000/second [doi]
"""

BIBTEX = """@article{key2023,
  title = {Análise cognitiva em contexto},
  author = {Silva, Ana and Costa, Bruno},
  year = {2022},
  journal = {Revista X},
  doi = {10.3000/xyz},
  keywords = {cognição, educação}
}
"""


def test_detecta_medline_por_conteudo():
    assert detectar_formato_conteudo(MEDLINE) == "medline"


def test_nbib_defere_para_conteudo():
    # a extensão .nbib não força mais "ris"; quem decide é o conteúdo
    assert detectar_formato("pubmed_result.nbib") is None
    assert detectar_formato("export.ris") == "ris"
    assert detectar_formato("export.bib") == "bibtex"


def test_parse_medline_campos():
    regs = parse_medline(MEDLINE)
    assert len(regs) == 2
    r = regs[0]
    assert r["titulo"] == "Cognitive analysis of decision making in clinical practice: a study."
    assert r["autores"] == "Smith, John A; Doe, Jane"  # usa FAU (nome completo)
    assert r["ano"] == 2023
    assert r["doi"] == "10.1000/example123"
    assert "clinical decision making" in r["resumo"]
    assert r["palavras_chaves"] == "cognition; decision making"
    assert r["titulo_periodico"] == "Journal of Medical Education"
    assert r["idioma"] == "eng"
    assert r["link"] == "https://pubmed.ncbi.nlm.nih.gov/12345678/"
    # 2º registro: DOI via LID, periódico via JT
    assert regs[1]["doi"] == "10.2000/second"
    assert regs[1]["ano"] == 2021


def test_analisar_arquivo_nbib_ok():
    r = analisar_arquivo("pubmed_result.nbib", MEDLINE.encode("utf-8"))
    assert r["ok"] is True
    assert r["formato"] == "medline"
    assert r["n"] == 2


def test_analisar_arquivo_bib_ok():
    r = analisar_arquivo("zotero_export.bib", BIBTEX.encode("utf-8"))
    assert r["ok"] is True
    assert r["formato"] == "bibtex"
    assert r["n"] == 1
