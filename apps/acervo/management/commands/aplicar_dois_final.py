"""Aplica o plano final de correção de DOIs em DUAS FASES (limpa -> grava).

Por que duas fases: os DOIs estão deslocados em cadeia (A tem o DOI de B, B o de
C...). Setar direto colidiria com a UNIQUE. Zerando todos os envolvidos primeiro
e gravando depois, nenhuma colisão transitória ocorre.

Entrada: CSV com colunas `id,acao,doi`  (acao = SET|CLEAR).

Salvaguardas:
  - Só mexe nos ids do CSV.
  - Antes de gravar, confere que nenhum alvo SET colide com artigo FORA do plano.
  - `--dry-run` (padrão) reverte tudo. `--apply` grava (faça pg_dump antes).
"""

from __future__ import annotations

import csv
import re
from collections import Counter
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.acervo.models import Artigo


def nd(x: str) -> str:
    if not x:
        return ""
    m = re.search(r"10\.\d{4,9}/[^\s\";]+", str(x).lower())
    return m.group(0).rstrip(".") if m else ""


class Command(BaseCommand):
    help = "Aplica correção de DOIs em duas fases a partir de um CSV (id,acao,doi)."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--csv", required=True)
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--apply", action="store_true")

    def handle(self, *args, **opts):
        path = Path(opts["csv"])
        apply = opts["apply"]
        dry = opts["dry_run"] or not apply
        if not path.exists():
            raise CommandError(f"CSV não encontrado: {path}")

        rows = list(csv.DictReader(open(path, encoding="utf-8")))
        ids = [int(r["id"]) for r in rows]
        sets = {int(r["id"]): nd(r["doi"]) for r in rows if r["acao"] == "SET"}
        clears = {int(r["id"]) for r in rows if r["acao"] == "CLEAR"}

        # Colisão com artigo FORA do plano?
        for rid, doi in sets.items():
            conflito = Artigo.objects.filter(doi=doi).exclude(pk__in=ids).first()
            if conflito:
                raise CommandError(
                    f"ABORTADO: id={rid} quer {doi}, mas já existe no artigo {conflito.pk} (fora do plano)."
                )

        log = Counter()
        with transaction.atomic():
            # FASE A: zera todos os envolvidos
            for art in Artigo.objects.filter(pk__in=ids):
                if art.doi:
                    art.doi = None
                    art.save(update_fields=["doi"])
                    log["fase_a:zerado"] += 1
            # FASE B: grava os SET
            for rid, doi in sets.items():
                art = Artigo.objects.get(pk=rid)
                art.doi = doi
                art.save(update_fields=["doi"])
                log["fase_b:gravado"] += 1
            log["clear:mantido_vazio"] = len(clears)

            if dry:
                self.stdout.write(self.style.WARNING("DRY-RUN: revertendo (nada gravado)."))
                transaction.set_rollback(True)

        self.stdout.write(self.style.SUCCESS("\n=== Aplicação final de DOIs ==="))
        for k in sorted(log):
            self.stdout.write(f"  {k:24s} {log[k]}")
        total = Artigo.objects.exclude(doi__isnull=True).count()
        self.stdout.write(f"\n  Artigos com DOI agora: {total}")
        self.stdout.write(
            self.style.SUCCESS(
                f"  Modo: {'APLICADO' if (apply and not opts['dry_run']) else 'DRY-RUN'}"
            )
        )
