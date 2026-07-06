"""Corrige links de acesso com **esquema embutido** no corpus ANCO.

Alguns exports do Zotero gravaram o campo URL como `https://doi.org/` colado a
uma URL já completa (`https://doi.org/https://doi.org/10.x/y` ou
`https://doi.org/https://journals.sagepub.com/...`). O import copiou fielmente,
propagando o link quebrado para `ItemCorpus.link` e `Artigo.link_acesso`.

Este comando reaplica `parsers.normalizar_url` — recupera a URL interna real —
aos itens afetados e propaga ao `Artigo` (respeita `eh_legado`). O DOI não é
tocado (já está correto). Idempotente; `--dry-run` só relata.

Uso:
    manage.py corrigir_links --projeto piloto-revisao-anco [--dry-run]
    manage.py corrigir_links            # todos os projetos
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.anco.importacao import sincronizar_artigo
from apps.anco.models import ItemCorpus, ProjetoANCO
from apps.anco.parsers import normalizar_url

# URL com um segundo esquema http(s) embutido no meio.
_EMBUTIDA = r"https?://[^\s]*https?://"


class Command(BaseCommand):
    help = "Corrige links com esquema embutido (https://doi.org/https://…) no corpus ANCO."

    def add_arguments(self, parser):
        parser.add_argument("--projeto", help="slug do projeto (default: todos)")
        parser.add_argument("--dry-run", action="store_true", help="só relata, não grava")

    def handle(self, *args, **opts):
        dry = opts["dry_run"]
        itens = ItemCorpus.objects.exclude(link="").filter(link__regex=_EMBUTIDA)
        if opts["projeto"]:
            proj = ProjetoANCO.objects.get(slug=opts["projeto"])
            itens = itens.filter(projeto=proj)

        self.stdout.write(f"{itens.count()} item(ns) com link de esquema embutido.")
        corrigidos = 0
        for it in itens.order_by("pk"):
            novo = normalizar_url(it.link)
            if novo == it.link:  # nada a fazer (salvaguarda de idempotência)
                continue
            corrigidos += 1
            self.stdout.write(f"  {it.pk}: {it.link}\n     → {novo}")
            if not dry:
                it.link = novo
                it.save(update_fields=["link"])
                sincronizar_artigo(it)  # propaga p/ Artigo (respeita eh_legado)

        verbo = "seriam" if dry else "foram"
        self.stdout.write(
            self.style.SUCCESS(
                f"\n{'[DRY-RUN] ' if dry else ''}{corrigidos} link(s) {verbo} corrigido(s)."
            )
        )
