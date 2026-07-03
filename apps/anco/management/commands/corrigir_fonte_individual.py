"""Backfill: reatribui itens do balde genérico "Artigos individuais" à base REAL
declarada no artigo, para a estatística do corpus ficar por base (RIAnCo, PubMed,
Redalyc…) e não pela forma de inclusão.

Idempotente. Use `--dry-run` para conferir antes de aplicar.

    python manage.py corrigir_fonte_individual --projeto piloto-revisao-anco --dry-run
    python manage.py corrigir_fonte_individual --projeto piloto-revisao-anco
"""

from __future__ import annotations

from collections import Counter

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count, Q

from apps.anco.models import FonteImport

GENERICO = "Artigos individuais"


def _base_do_artigo(art):
    """Chave da base real do artigo, ou None se ele não declara base alguma."""
    if art is None:
        return None
    if art.base_consulta_id:
        return ("fk", art.base_consulta_id)
    outra = (art.outra_base_consulta or "").strip()
    if outra:
        return ("outra", outra[:200])
    return None


def _chave_get_or_create(base):
    kind, val = base
    if kind == "fk":
        return {"base_consulta_id": val, "outra_base": ""}
    return {"base_consulta": None, "outra_base": val}


def _filtro_mesma_base(base):
    kind, val = base
    if kind == "fk":
        return Q(base_consulta_id=val)
    return Q(base_consulta__isnull=True, outra_base=val)


class Command(BaseCommand):
    help = "Reatribui itens de 'Artigos individuais' à base real do artigo (estatística por base)."

    def add_arguments(self, parser):
        parser.add_argument("--projeto", help="slug do projeto (padrão: todos)")
        parser.add_argument(
            "--dry-run", action="store_true", help="apenas relata, não altera nada"
        )

    def handle(self, *args, **opts):
        dry = opts["dry_run"]
        genericas = FonteImport.objects.filter(
            outra_base=GENERICO, base_consulta__isnull=True
        ).select_related("projeto", "criado_por")
        if opts.get("projeto"):
            genericas = genericas.filter(projeto__slug=opts["projeto"])

        movidos: Counter[str] = Counter()
        sem_base = 0
        ja_na_base = 0
        fontes_criadas: set[int] = set()
        fontes_removidas = 0

        with transaction.atomic():
            for fonte in genericas:
                itens = list(fonte.itens.select_related("artigo", "artigo__base_consulta").all())
                for item in itens:
                    base = _base_do_artigo(item.artigo)
                    if base is None:
                        sem_base += 1
                        continue
                    # Já pertence a uma fonte dessa base (ex.: também importado em
                    # lote)? Só solta do balde genérico, sem duplicar a base.
                    dup = (
                        item.origem_fontes.exclude(pk=fonte.pk)
                        .filter(_filtro_mesma_base(base))
                        .exists()
                    )
                    rotulo = base[1] if base[0] == "outra" else _rotulo_fk(item.artigo)
                    if dup:
                        ja_na_base += 1
                        if not dry:
                            item.origem_fontes.remove(fonte)
                        continue
                    if dry:
                        movidos[rotulo] += 1
                        continue
                    alvo, criada = FonteImport.objects.get_or_create(
                        projeto=fonte.projeto,
                        criado_por=fonte.criado_por,
                        individual=True,
                        defaults={"importado_em": fonte.importado_em},
                        **_chave_get_or_create(base),
                    )
                    if criada:
                        fontes_criadas.add(alvo.pk)
                    item.origem_fontes.remove(fonte)
                    item.origem_fontes.add(alvo)
                    movidos[rotulo] += 1

                # Balde vazio depois das movimentações: remove. Ainda com itens
                # (artigos sem base): mantém, mas marca como individual.
                if not dry:
                    if not fonte.itens.exists():
                        fonte.delete()
                        fontes_removidas += 1
                    elif not fonte.individual:
                        fonte.individual = True
                        fonte.save(update_fields=["individual"])

            # Reconta n_lidos/n_novos das fontes individuais tocadas (cosmético no
            # admin; a estatística usa a contagem viva de itens).
            if not dry:
                recontar = FonteImport.objects.filter(individual=True)
                if opts.get("projeto"):
                    recontar = recontar.filter(projeto__slug=opts["projeto"])
                for f in recontar.annotate(_n=Count("itens", filter=Q(itens__removido=False))):
                    if f.n_novos != f._n or f.n_lidos != f._n:
                        f.n_lidos = f.n_novos = f._n
                        f.save(update_fields=["n_lidos", "n_novos"])

            if dry:
                transaction.set_rollback(True)

        self.stdout.write(self.style.MIGRATE_HEADING("Reatribuição por base:"))
        for base, n in sorted(movidos.items(), key=lambda x: (-x[1], x[0])):
            self.stdout.write(f"  {n:4d}  {base}")
        self.stdout.write(
            f"itens já na base (só soltos do balde): {ja_na_base} · "
            f"sem base no artigo (mantidos): {sem_base}"
        )
        self.stdout.write(
            f"fontes de base criadas: {len(fontes_criadas)} · baldes vazios removidos: "
            f"{fontes_removidas}"
        )
        if dry:
            self.stdout.write(self.style.WARNING("DRY-RUN: nada foi gravado."))
        else:
            self.stdout.write(self.style.SUCCESS("Concluído."))


def _rotulo_fk(art) -> str:
    return art.base_consulta.nome if art and art.base_consulta_id else "(base)"
