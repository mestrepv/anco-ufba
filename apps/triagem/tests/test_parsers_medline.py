"""Triagem PRISMA — parser MEDLINE (.nbib) e BibTeX (.bib) no import."""

from apps.triagem.importacao import (
    analisar_arquivo,
    detectar_formato,
    detectar_formato_conteudo,
    parse_medline,
)

MEDLINE = """PMID- 12345678
TI  - Cognitive analysis of decision making in clinical
      practice: a study.
AB  - This study examines cognitive processes.
FAU - Smith, John A
AU  - Smith JA
FAU - Doe, Jane
DP  - 2023 Jun
JT  - Journal of Medical Education
LA  - eng
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
  title = {Triagem e cognição},
  author = {Silva, Ana and Costa, Bruno},
  year = {2022},
  journal = {Revista X},
  doi = {10.3000/xyz}
}
"""


def test_detecta_medline():
    assert detectar_formato_conteudo(MEDLINE) == "medline"
    assert detectar_formato("pubmed.nbib") is None  # decide por conteúdo


def test_parse_medline_campos():
    regs = parse_medline(MEDLINE)
    assert len(regs) == 2
    r = regs[0]
    assert r["titulo"] == "Cognitive analysis of decision making in clinical practice: a study."
    assert r["autores"] == "Smith, John A; Doe, Jane"
    assert r["ano"] == 2023
    assert r["doi"] == "10.1000/example123"
    assert r["palavras_chaves"] == "cognition; decision making"
    assert r["titulo_periodico"] == "Journal of Medical Education"
    assert regs[1]["doi"] == "10.2000/second"


def test_analisar_arquivo_nbib_e_bib():
    a = analisar_arquivo("pubmed.nbib", MEDLINE.encode("utf-8"))
    assert a["ok"] and a["formato"] == "medline" and a["n"] == 2
    b = analisar_arquivo("zotero.bib", BIBTEX.encode("utf-8"))
    assert b["ok"] and b["formato"] == "bibtex" and b["n"] == 1
