"""Reprocessa os arquivos das fontes de import e **preenche campos vazios** do
corpus (resumo, palavras-chave, autores, etc.).

Motivação: parsers antigos (CSV do Zotero sem mapear `Abstract Note`; `.nbib` do
PubMed que colapsava em 1 registro por causa do CRLF) deixaram itens sem resumo.
O import normal faz dedup por `identificador` e **não** backfilla campos vazios
numa reimportação — daí este comando.

Regras de segurança:
- Só preenche campo **vazio** com valor **não-vazio** do arquivo; nunca sobrescreve.
- Nunca mexe em campos de identidade (`doi`/`isbn`/`titulo`) — não muda a dedup.
- Cria os registros que faltam (ex.: os ~56 do PubMed `.nbib` corrigido) via o
  fluxo normal de import (promove ao acervo). O acervo legado nunca é tocado.
- `--dry-run` só relata; idempotente (rodar 2x não muda nada na 2ª vez).

Uso:
    manage.py backfill_conteudo --projeto piloto-revisao-anco [--dry-run]
    manage.py backfill_conteudo            # todos os projetos
"""

from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.anco import parsers
from apps.anco.dedup import chave_dedup, normalizar_doi
from apps.anco.importacao import importar_para_fonte, sincronizar_artigo
from apps.anco.models import FonteImport, ItemCorpus, ProjetoANCO

# Campos de conteúdo que podem ser backfillados (NÃO incluem doi/isbn/titulo,
# que definem a identidade/dedup do item).
_CAMPOS_BACKFILL = (
    "resumo",
    "palavras_chaves",
    "autores",
    "titulo_periodico",
    "idioma",
    "link",
    "tipo",
)


class Command(BaseCommand):
    help = "Reprocessa arquivos das fontes e preenche campos vazios do corpus ANCO."

    def add_arguments(self, parser):
        parser.add_argument("--projeto", help="slug do projeto (default: todos)")
        parser.add_argument("--dry-run", action="store_true", help="só relata, não grava")

    def handle(self, *args, **opts):
        dry = opts["dry_run"]
        fontes = FonteImport.objects.exclude(arquivo="").filter(arquivo__isnull=False)
        if opts["projeto"]:
            proj = ProjetoANCO.objects.get(slug=opts["projeto"])
            fontes = fontes.filter(projeto=proj)

        tot_criados = tot_backfill = 0
        for fonte in fontes.select_related("projeto").order_by("pk"):
            criados, backfill = self._processar_fonte(fonte, dry)
            tot_criados += criados
            tot_backfill += backfill
            if criados or backfill:
                self.stdout.write(
                    f"  fonte {fonte.pk} ({fonte.base_nome}/{fonte.formato}): "
                    f"+{criados} novo(s), {backfill} resumo(s)/campo(s) preenchido(s)"
                )

        verbo = "seriam" if dry else "foram"
        self.stdout.write(
            self.style.SUCCESS(
                f"\n{'[DRY-RUN] ' if dry else ''}Total: {tot_criados} item(ns) {verbo} "
                f"criado(s), {tot_backfill} campo(s) {verbo} preenchido(s)."
            )
        )

    def _parse_fonte(self, fonte: FonteImport) -> list[dict] | None:
        try:
            fonte.arquivo.open("rb")
            raw = fonte.arquivo.read()
        finally:
            fonte.arquivo.close()
        texto = parsers.decodificar(raw)
        formato = fonte.formato or parsers.detectar_formato_conteudo(texto)
        if formato not in parsers.FORMATOS:
            self.stderr.write(f"  fonte {fonte.pk}: formato indefinido, pulando")
            return None
        try:
            return parsers.parse_conteudo(texto, formato)
        except Exception as exc:  # noqa: BLE001
            self.stderr.write(f"  fonte {fonte.pk}: erro ao parsear ({exc}), pulando")
            return None

    def _processar_fonte(self, fonte: FonteImport, dry: bool) -> tuple[int, int]:
        registros = self._parse_fonte(fonte)
        if not registros:
            return 0, 0
        projeto = fonte.projeto

        # 1) Cria os registros que faltam (ex.: PubMed .nbib corrigido). Idempotente:
        #    itens existentes só re-vinculam a fonte, sem duplicar.
        criados = 0
        if dry:
            for bruto in registros:
                if not (bruto.get("titulo") or "").strip():
                    continue
                ident = chave_dedup(
                    normalizar_doi(bruto.get("doi") or ""),
                    (bruto.get("isbn") or "").strip(),
                    bruto["titulo"].strip(),
                    bruto.get("ano"),
                    (bruto.get("titulo_periodico") or "").strip(),
                )
                if not ItemCorpus.objects.filter(projeto=projeto, identificador=ident).exists():
                    criados += 1
        else:
            with transaction.atomic():
                criados = importar_para_fonte(fonte, registros).novos

        # 2) Backfill de campos vazios nos itens existentes.
        backfill = 0
        for bruto in registros:
            titulo = (bruto.get("titulo") or "").strip()
            if not titulo:
                continue
            ident = chave_dedup(
                normalizar_doi(bruto.get("doi") or ""),
                (bruto.get("isbn") or "").strip(),
                titulo,
                bruto.get("ano"),
                (bruto.get("titulo_periodico") or "").strip(),
            )
            item = ItemCorpus.objects.filter(projeto=projeto, identificador=ident).first()
            if item is None:
                continue
            mudou = []
            for campo in _CAMPOS_BACKFILL:
                atual = (getattr(item, campo) or "").strip()
                novo = (bruto.get(campo) or "").strip()
                if not atual and novo:
                    setattr(item, campo, novo)
                    mudou.append(campo)
            if mudou:
                backfill += 1
                if not dry:
                    item.save(update_fields=mudou)
                    sincronizar_artigo(item)  # propaga p/ Artigo (respeita eh_legado)
        return criados, backfill
