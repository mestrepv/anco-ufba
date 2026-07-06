"""Recupera **resumos truncados ou vazios** do corpus ANCO via DOI.

Motivação: itens importados de exports CSV do Zotero salvos a partir da
*listagem de resultados* da Sage (e bases similares) trazem só o *snippet* do
abstract (~250 caracteres terminando em "..."), não o abstract completo. Este
comando busca o abstract inteiro por DOI — **Crossref** (metadado oficial) com
fallback para **OpenAlex** (melhor cobertura de abstract) — e preenche.

Regras de segurança:
- Só age em itens cujo resumo está **truncado** (termina em "...") ou **vazio**,
  e que **tenham DOI**. Nunca sobrescreve um resumo completo já existente.
- Só grava se o abstract recuperado for **mais longo** que o atual (evita troca
  por versão pior) e não estiver ele mesmo truncado.
- Nunca toca campos de identidade (doi/isbn/titulo) nem o acervo legado.
- Propaga o novo resumo ao `Artigo` vinculado via `sincronizar_artigo`.
- `--dry-run` só relata; idempotente (rodar 2x não muda nada na 2ª vez).

Uso:
    manage.py backfill_resumos --projeto piloto-revisao-anco [--dry-run]
    manage.py backfill_resumos --projeto piloto-revisao-anco --so-truncados
    manage.py backfill_resumos            # todos os projetos
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.acervo.services.abstracts import esta_truncado as _esta_truncado
from apps.acervo.services.abstracts import melhor_abstract as buscar_abstract
from apps.anco.importacao import sincronizar_artigo
from apps.anco.models import ItemCorpus, ProjetoANCO


class Command(BaseCommand):
    help = "Recupera resumos truncados/vazios do corpus ANCO via Crossref/OpenAlex."

    def add_arguments(self, parser):
        parser.add_argument("--projeto", help="slug do projeto (default: todos)")
        parser.add_argument("--dry-run", action="store_true", help="só relata, não grava")
        parser.add_argument(
            "--so-truncados",
            action="store_true",
            help="ignora os de resumo vazio; só reprocessa os truncados",
        )

    def handle(self, *args, **opts):
        dry = opts["dry_run"]
        itens = ItemCorpus.objects.filter(removido=False).exclude(doi="")
        if opts["projeto"]:
            proj = ProjetoANCO.objects.get(slug=opts["projeto"])
            itens = itens.filter(projeto=proj)

        # Truncados sempre; vazios opcionalmente. Filtro fino (truncado exato) é
        # feito em Python — o SQL só reduz o conjunto.
        if opts["so_truncados"]:
            itens = itens.exclude(resumo="")
        alvos = [it for it in itens if it.resumo.strip() == "" or _esta_truncado(it.resumo)]

        self.stdout.write(f"{len(alvos)} item(ns) candidato(s) (truncado ou vazio, com DOI).")
        preenchidos = falhas = ignorados = 0
        por_fonte = {"crossref": 0, "openalex": 0}

        for it in alvos:
            atual = it.resumo.strip()
            novo, fonte = buscar_abstract(it.doi)
            if not novo:
                falhas += 1
                self.stdout.write(f"  ✗ {it.pk} sem abstract recuperável (DOI {it.doi})")
                continue
            # Só melhora: novo tem de superar o atual em tamanho.
            if len(novo) <= len(atual):
                ignorados += 1
                continue
            preenchidos += 1
            por_fonte[fonte] += 1
            self.stdout.write(
                f"  ✓ {it.pk} [{fonte}] {len(atual)}→{len(novo)} chars — {it.titulo[:55]}"
            )
            if not dry:
                it.resumo = novo
                it.save(update_fields=["resumo"])
                sincronizar_artigo(it)  # propaga p/ Artigo (respeita eh_legado)

        verbo = "seriam" if dry else "foram"
        self.stdout.write(
            self.style.SUCCESS(
                f"\n{'[DRY-RUN] ' if dry else ''}{preenchidos} resumo(s) {verbo} "
                f"preenchido(s) (crossref={por_fonte['crossref']}, "
                f"openalex={por_fonte['openalex']}); {ignorados} sem ganho, "
                f"{falhas} sem abstract."
            )
        )
