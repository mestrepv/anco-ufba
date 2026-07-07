"""Limpeza SEGURA dos vocabulários Epistemologia e Teoria (ANCO).

O vocabulário foi gerado dos valores livres do legado e ficou poluído com
compostos (`A; B; C`), glosas entre parênteses e duplicatas de caixa/acento.

Este comando aplica só o de **baixo risco**, sem tocar em NENHUMA análise
(legado é intocável — os valores históricos permanecem):

  1. divide compostos separados por `;` em termos atômicos;
  2. remove glosas entre parênteses (canonicaliza `X (…)` → `X`);
  3. unifica duplicatas exatas por caixa/acento;
  4. garante os termos atômicos como ATIVOS e DESATIVA os compostos/glosados/
     duplicados (somem do picker; continuam no banco p/ o legado exibir).

O ambíguo (compostos com `/`, quase-duplicatas semânticas) NÃO é mexido —
sai num CSV para revisão humana.

Uso:
  manage.py limpar_vocabulario_anco            # dry-run (não grava)
  manage.py limpar_vocabulario_anco --apply    # aplica
  manage.py limpar_vocabulario_anco --csv-dir /caminho   # onde salvar os CSVs
"""

from __future__ import annotations

import csv
import re
import unicodedata
from collections import Counter
from difflib import SequenceMatcher

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.vocabulario.models import TermoVocabulario, Vocabulario

VOCABS = ["epistemologia", "teoria"]
_GLOSA = re.compile(r"\s*\([^)]*\)")
_SEP = re.compile(r"\s*[;/,]\s*")  # separadores de composto (Google Forms): ; / ,


def _norm(s: str) -> str:
    n = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9/ ]+", " ", n.lower())).strip()


def _sem_glosa(s: str) -> str:
    """Remove glosas entre parênteses e pontuação/separadores nas pontas."""
    return re.sub(r"\s+", " ", _GLOSA.sub("", s or "")).strip(" .;,-·").strip()


def _uso(vocab_cod: str) -> Counter:
    from apps.acervo.models import Analise

    rel = vocab_cod  # M2M chamado igual ao código
    c: Counter = Counter()
    for a in Analise.objects.all().prefetch_related(rel):
        for t in getattr(a, rel).all():
            c[t.pk] += 1
    return c


class Command(BaseCommand):
    help = "Limpeza segura dos vocabulários Epistemologia/Teoria (não toca análises)."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="grava (default: dry-run)")
        parser.add_argument("--csv-dir", default="/tmp", help="pasta p/ os CSVs de revisão")

    def handle(self, *args, **opts):
        apply = opts["apply"]
        with transaction.atomic():
            for cod in VOCABS:
                self._processar(cod, apply, opts["csv_dir"])
            if not apply:
                transaction.set_rollback(True)
                self.stdout.write(self.style.WARNING("\n[DRY-RUN] Nada gravado. Use --apply."))

    def _processar(self, cod: str, apply: bool, csv_dir: str):
        v = Vocabulario.objects.filter(codigo=cod).first()
        if not v:
            return
        termos = list(TermoVocabulario.objects.filter(vocabulario=v))
        uso = _uso(cod)

        # Canônicos atômicos existentes: termo "limpo" (sem ';' '/' e sem glosa),
        # 1 por forma normalizada (preferindo o mais usado / melhor caixa).
        canon: dict[str, TermoVocabulario] = {}
        for t in sorted(termos, key=lambda x: (-uso.get(x.pk, 0), x.nome)):
            base = _sem_glosa(t.nome)
            limpo = not _SEP.search(base) and base == t.nome.strip()
            if limpo and base:
                canon.setdefault(_norm(base), t)

        # ATOMIZAR: '/' e ';' eram limitação do Google Forms (escolha única);
        # aqui o multi-select deixa o analista marcar cada componente. Então
        # dividimos os compostos em termos atômicos, removemos glosas e unificamos
        # duplicatas exatas. Compostos/glosados/duplicados são DESATIVADOS (somem
        # do picker; permanecem p/ o legado exibir). NENHUMA análise é tocada.
        criados: list[str] = []
        desativar: list[TermoVocabulario] = []

        def _garantir(nome: str) -> None:
            nome = nome.strip()
            if not nome:
                return
            n = _norm(nome)
            if n in canon:
                termo = canon[n]
                if getattr(termo, "pk", None) and not termo.ativo and apply:
                    termo.ativo = True
                    termo.save(update_fields=["ativo"])
                return
            criados.append(nome)
            canon[n] = (
                TermoVocabulario.objects.create(vocabulario=v, nome=nome, ativo=True)
                if apply
                else TermoVocabulario(vocabulario=v, nome=nome, ativo=True)
            )

        for t in termos:
            base = _sem_glosa(t.nome)  # remove glosa ANTES de dividir (glosa pode ter ';')
            composto = bool(_SEP.search(base))
            glosado = base != t.nome.strip()
            if composto or glosado:
                for parte in _SEP.split(base):
                    _garantir(parte)
                desativar.append(t)
            else:
                c = canon.get(_norm(base))
                if c and getattr(c, "pk", None) != t.pk:
                    desativar.append(t)  # duplicata exata (caixa/acento)

        desat_pks = {t.pk for t in desativar if t.pk}
        if apply and desat_pks:
            TermoVocabulario.objects.filter(pk__in=desat_pks).update(ativo=False)

        ativos_final = [t for t in termos if t.pk not in desat_pks]
        ativos_final += [c for c in canon.values() if getattr(c, "pk", None) is None]
        revisao = self._revisar(v, ativos_final, uso, csv_dir, cod, apply)

        atomicos = sorted(
            {_norm(c.nome): c.nome for c in canon.values()}.values(), key=str.lower
        )
        self.stdout.write(self.style.MIGRATE_HEADING(f"\n=== {cod} ==="))
        self.stdout.write(f"  termos atuais: {len(termos)}")
        self.stdout.write(f"  atômicos a criar: {len(criados)}")
        self.stdout.write(f"  compostos/glosa/duplicata a desativar: {len(desativar)}")
        self.stdout.write(
            f"  vocabulário atômico resultante (canônicos): {len(atomicos)}"
        )
        self.stdout.write("  amostra atômicos: " + ", ".join(atomicos[:18]))
        self.stdout.write(f"  ainda para revisão humana (fuzzy/vírgula): {revisao}")

    def _revisar(self, v, ativos, uso, csv_dir, cod, apply) -> str:
        """CSV com '/'-compostos e clusters de quase-duplicatas (sim>=.86)."""
        nomes = [(t, t.nome) for t in ativos if (t.nome or "").strip()]
        linhas = []
        # Compostos por vírgula — separador ambíguo (pode ser parte do nome),
        # então não atomizamos automaticamente: vão para decisão humana.
        for t, nome in nomes:
            if "," in nome:
                linhas.append((nome, uso.get(getattr(t, "pk", 0), 0), "composto ','", ""))
        # quase-duplicatas
        vistos = set()
        for i in range(len(nomes)):
            a = _norm(nomes[i][1])
            grp = []
            for j in range(i + 1, len(nomes)):
                b = _norm(nomes[j][1])
                if not a or not b:
                    continue
                if SequenceMatcher(None, a, b).ratio() >= 0.86:
                    grp.append(nomes[j][1])
            if grp and nomes[i][1] not in vistos:
                vistos.add(nomes[i][1])
                for g in grp:
                    vistos.add(g)
                linhas.append(
                    (nomes[i][1], uso.get(getattr(nomes[i][0], "pk", 0), 0),
                     "quase-duplicata", " | ".join(grp))
                )
        path = f"{csv_dir.rstrip('/')}/revisao_{cod}.csv"
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(
                ["termo", "usos", "motivo", "parece igual a",
                 "decisao (manter/unir_em/dividir_em/desativar)"]
            )
            for termo, n, motivo, similares in linhas:
                w.writerow([termo, n, motivo, similares, ""])
        return f"{len(linhas)} linha(s) → {path}"
