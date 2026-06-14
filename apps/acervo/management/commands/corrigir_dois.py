"""Corrige DOIs ERRADOS de Artigos do acervo, a partir de um CSV auditado.

Contexto: o comando `aplicar_dois_recuperados` aplicou DOIs vindos de um
cruzamento de referencial que, para vários registros (sobretudo títulos
não-ingleses), atribuiu o DOI de OUTRO artigo. Esta correção usa um CSV
auditado (WoS + conflitos_doi + Crossref) com o DOI correto por `id`.

Decisões (coluna `decisao` do CSV):
  CORRIGIR -> troca `doi_atual` por `doi_novo` (só se o DOI atual ainda for o
              esperado, e se o novo não colidir com outro Artigo).
  REVISAR  -> NÃO toca (decisão humana — possíveis traduções/cross-lingual).
  MANTER   -> ignorado.

Salvaguardas:
  - Casa por `id` (preciso) e confere que `doi_atual` no banco == CSV (anti-drift).
  - Se `doi_novo` já existe em OUTRO Artigo, loga colisão e PULA (pode indicar
    duplicata real no acervo — decisão humana).
  - `--dry-run` (padrão) roda em transação revertida: NADA é gravado.
  - Só grava com `--apply`. FAÇA pg_dump antes (ver CLAUDE.md §11).

Uso:
  python manage.py corrigir_dois --csv /app/prod_doi_correcoes.csv --dry-run
  python manage.py corrigir_dois --csv /app/prod_doi_correcoes.csv --apply
"""

from __future__ import annotations

import csv
import re
from collections import Counter
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.acervo.models import Artigo


def ndoi(x: str) -> str:
    if not x:
        return ""
    m = re.search(r"10\.\d{4,9}/[^\s\";]+", str(x).lower())
    return m.group(0).rstrip(".") if m else ""


class Command(BaseCommand):
    help = "Corrige DOIs errados de Artigos a partir de um CSV auditado (id, decisao, doi_atual, doi_novo)."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--csv", required=True, help="CSV auditado (prod_doi_correcoes.csv).")
        parser.add_argument(
            "--dry-run", action="store_true", help="Transação revertida (nada gravado)."
        )
        parser.add_argument(
            "--apply", action="store_true", help="Grava de fato. Exige pg_dump antes."
        )

    def handle(self, *args, **opts):
        path = Path(opts["csv"])
        apply = opts["apply"]
        dry = opts["dry_run"] or not apply
        if not path.exists():
            raise CommandError(f"CSV não encontrado: {path}")

        rows = [
            r
            for r in csv.DictReader(open(path, encoding="utf-8"))
            if r.get("decisao") == "CORRIGIR"
        ]
        log = Counter()
        mudancas: list[str] = []

        with transaction.atomic():
            for r in rows:
                rid = (r.get("id") or "").strip()
                d_at = ndoi(r.get("doi_atual"))
                d_novo = ndoi(r.get("doi_novo"))
                if not rid or not d_novo:
                    log["pulado:linha_incompleta"] += 1
                    continue
                try:
                    art = Artigo.objects.get(pk=int(rid))
                except Artigo.DoesNotExist:
                    log["pulado:id_inexistente"] += 1
                    continue

                atual_banco = ndoi(art.doi or "")
                if atual_banco != d_at:
                    # o DOI no banco já não é o que auditamos -> não mexe (anti-drift)
                    log["pulado:doi_mudou_desde_auditoria"] += 1
                    continue
                if atual_banco == d_novo:
                    log["ja_correto"] += 1
                    continue
                # colisão: o DOI novo já existe em outro artigo?
                if Artigo.objects.filter(doi=d_novo).exclude(pk=art.pk).exists():
                    log["pulado:colisao_doi_novo_em_outro"] += 1
                    self.stdout.write(
                        self.style.WARNING(
                            f"  COLISÃO id={art.pk}: novo DOI {d_novo} já existe em outro artigo (poss. duplicata) — PULADO"
                        )
                    )
                    continue

                mudancas.append(f"  id={art.pk}: {d_at}  ->  {d_novo}  | {art.titulo[:55]}")
                art.doi = d_novo
                try:
                    with transaction.atomic():
                        art.save(update_fields=["doi"])
                    log["corrigido"] += 1
                except Exception as e:  # noqa: BLE001
                    log["erro_save"] += 1
                    self.stdout.write(self.style.ERROR(f"  erro id={art.pk}: {e}"))

            if dry:
                self.stdout.write(self.style.WARNING("\nDRY-RUN: revertendo (nada foi gravado)."))
                transaction.set_rollback(True)

        self.stdout.write(self.style.SUCCESS("\n=== Correção de DOIs ==="))
        for k in sorted(log):
            self.stdout.write(f"  {k:38s} {log[k]}")
        self.stdout.write("\n  Mudanças propostas:")
        for m in mudancas[:60]:
            self.stdout.write(m)
        if len(mudancas) > 60:
            self.stdout.write(f"  ... (+{len(mudancas) - 60})")
        modo = "APLICADO" if (apply and not opts["dry_run"]) else "DRY-RUN (sem gravar)"
        self.stdout.write(self.style.SUCCESS(f"\n  Modo: {modo}"))
