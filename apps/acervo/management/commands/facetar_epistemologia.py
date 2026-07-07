"""Faceta o vocabulário 'epistemologia': separa o balaio em paradigma ×
metodologia × disciplina × aplicação — SEM apagar nada e SEM tocar análises.

Alinha o campo Epistemologia à distinção da própria Fróes (epistemologia ≠
método ≠ disciplina), respeitando as formas como aparecem na literatura. O
picker de Epistemologia passa a oferecer só os PARADIGMAS; método/disciplina/
aplicação ficam classificados (para futuros campos) mas fora daquele picker;
não-termos vão para 'lixo'. Totalmente reversível (`--desfazer` limpa o grupo).

  manage.py facetar_epistemologia            # dry-run (mostra a classificação)
  manage.py facetar_epistemologia --apply
  manage.py facetar_epistemologia --desfazer # limpa todos os grupos (reverte)
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter

from django.core.management.base import BaseCommand

from apps.vocabulario.models import TermoVocabulario, Vocabulario

G = TermoVocabulario.Grupo


def _n(s: str) -> str:
    x = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", x.lower()).strip()


# Regras por palavra-chave (ordem importa: 1ª que casar vence).
# Curadas a partir dos termos reais do acervo; as coordenadoras podem ajustar
# depois no admin (o campo `grupo` é editável termo a termo).
_REGRAS: list[tuple[str, list[str]]] = [
    (G.LIXO, ["nao claro", "nao identificada", "os metodos ajudaram", "topico nao"]),
    (G.DISCIPLINA, [
        "linguistica", "neuro", "psicolog", "psican", "bioquim", "matematica",
        "geograf", "juridic", "sociolog", "fisiolog", "eletrofisiol", "semantica",
        "neural", "informatica", "computacional", "complexidade de dinamica",
        "literatura", "pensamento e linguagem", "ciencia cognitiva", "cientifica",
        "psicolinguistica",
    ]),
    (G.APLICACAO, [
        "aplicada", "educacional", "pedagog", "gestao", "usabilidade", "design",
        "engenharia", "tecnolog", "saude", "clinica", "desenvolvimento de instrumento",
    ]),
    (G.METODOLOGIA, [
        "qualitativ", "quantitativ", "experiment", "etnograf", "revisao",
        "meta-analit", "metanalit", "mista", "estatistic", "metrica", "numerica",
        "modelagem", "descritiv", "analitica", "investigacao", "avaliacao",
        "bayesiana", "comparativ", "psicometr", "quantimetr", "descriptive research",
        "formal", "conjuncao de modelos", "raciocinio probabilistico",
    ]),
]


# Correções pontuais onde o heurístico erra (o grupo é editável no admin depois).
_OVERRIDES = {
    "metodologica": G.METODOLOGIA,
    "neuroconstrutivista": G.PARADIGMA,  # neuroconstrutivismo é postura, não campo
}


def _classificar(nome: str) -> str:
    n = _n(nome)
    if n in _OVERRIDES:
        return _OVERRIDES[n]
    for grupo, chaves in _REGRAS:
        if any(k in n for k in chaves):
            return grupo
    return G.PARADIGMA  # default: postura epistemológica


class Command(BaseCommand):
    help = "Faceta o vocabulário Epistemologia (paradigma × método × disciplina × aplicação)."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--desfazer", action="store_true", help="limpa os grupos")

    def handle(self, *args, **opts):
        v = Vocabulario.objects.filter(codigo="epistemologia").first()
        if not v:
            self.stdout.write("Vocabulário 'epistemologia' não existe.")
            return
        termos = list(TermoVocabulario.objects.filter(vocabulario=v))

        if opts["desfazer"]:
            n = TermoVocabulario.objects.filter(vocabulario=v).update(grupo="")
            self.stdout.write(self.style.WARNING(f"Revertido: grupo limpo em {n} termo(s)."))
            return

        # Classifica TODOS (inclusive compostos inativos, p/ completude), mas o
        # relatório e o picker só consideram os ATIVOS.
        por_grupo_ativo: dict[str, list[str]] = {}
        for t in termos:
            g = _classificar(t.nome)
            if t.ativo:
                por_grupo_ativo.setdefault(g, []).append(t.nome)
            if opts["apply"]:
                t.grupo = g
        if opts["apply"]:
            TermoVocabulario.objects.bulk_update(termos, ["grupo"])

        self.stdout.write(self.style.MIGRATE_HEADING("Classificação da Epistemologia (ativos):"))
        for g, _lbl in G.choices:
            nomes = sorted(por_grupo_ativo.get(g, []), key=str.lower)
            self.stdout.write(f"\n  [{g}] {len(nomes)} termo(s):")
            self.stdout.write("    " + ", ".join(nomes) if nomes else "    —")
        so_paradigma = len(por_grupo_ativo.get(G.PARADIGMA, []))
        self.stdout.write(
            self.style.SUCCESS(
                f"\nPicker de Epistemologia passará a mostrar {so_paradigma} paradigma(s) "
                f"(era {sum(len(v) for v in por_grupo_ativo.values())} no balaio)."
            )
        )
        if not opts["apply"]:
            self.stdout.write(self.style.WARNING("\n[DRY-RUN] Nada gravado. Use --apply."))
