"""Recupera **palavras-chave vazias** do corpus ANCO via DOI, sinalizando a origem.

Muitas importações (ex.: CSV do Zotero/Sage) vêm sem tags. Este comando busca
palavras-chave por DOI — *subjects* da **Crossref** (do editor) e, na ausência,
keywords algorítmicas da **OpenAlex** — e preenche `ItemCorpus.palavras_chaves`,
propagando ao `Artigo`.

Como NÃO são as palavras-chave do autor, o valor recebe um sufixo de procedência
(`… — via OpenAlex`), para não se confundir com as originais no acervo citável.

Regras de segurança:
- Só age em itens com `palavras_chaves` **vazio** e **DOI**, cujo `Artigo` **não é
  legado** (acervo curado é intocável). Nunca sobrescreve palavras existentes.
- Propaga ao `Artigo` via `sincronizar_artigo` (que também respeita `eh_legado`).
- `--dry-run` só relata; idempotente (o sufixo de origem deixa o campo não-vazio).

Uso:
    manage.py backfill_keywords --projeto piloto-revisao-anco [--dry-run]
    manage.py backfill_keywords            # todos os projetos
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.acervo.services.abstracts import FONTE_LABEL, melhor_keywords
from apps.anco.importacao import sincronizar_artigo
from apps.anco.models import ItemCorpus, ProjetoANCO


class Command(BaseCommand):
    help = "Recupera palavras-chave vazias do corpus ANCO via Crossref/OpenAlex (com procedência)."

    def add_arguments(self, parser):
        parser.add_argument("--projeto", help="slug do projeto (default: todos)")
        parser.add_argument("--dry-run", action="store_true", help="só relata, não grava")

    def handle(self, *args, **opts):
        dry = opts["dry_run"]
        itens = (
            ItemCorpus.objects.filter(removido=False, palavras_chaves="")
            .exclude(doi="")
            .exclude(artigo__eh_legado=True)  # legado é intocável
            .select_related("artigo")
        )
        if opts["projeto"]:
            proj = ProjetoANCO.objects.get(slug=opts["projeto"])
            itens = itens.filter(projeto=proj)

        alvos = list(itens.order_by("pk"))
        self.stdout.write(f"{len(alvos)} item(ns) sem palavras-chave (com DOI, não-legado).")
        preenchidos = falhas = 0
        por_fonte = {"crossref": 0, "openalex": 0}

        for it in alvos:
            termos, fonte = melhor_keywords(it.doi)
            if not termos:
                falhas += 1
                continue
            valor = "; ".join(termos) + f" — via {FONTE_LABEL[fonte]}"
            preenchidos += 1
            por_fonte[fonte] += 1
            self.stdout.write(f"  ✓ {it.pk} [{fonte}] {valor[:70]}")
            if not dry:
                it.palavras_chaves = valor
                it.save(update_fields=["palavras_chaves"])
                sincronizar_artigo(it)  # propaga p/ Artigo (respeita eh_legado)

        verbo = "seriam" if dry else "foram"
        self.stdout.write(
            self.style.SUCCESS(
                f"\n{'[DRY-RUN] ' if dry else ''}{preenchidos} campo(s) {verbo} "
                f"preenchido(s) (crossref={por_fonte['crossref']}, "
                f"openalex={por_fonte['openalex']}); {falhas} sem keywords."
            )
        )
