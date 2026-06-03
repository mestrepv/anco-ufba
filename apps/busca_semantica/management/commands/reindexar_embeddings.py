"""
Gera (ou regenera) embeddings para Artigo e Analise.

    manage.py reindexar_embeddings                # apenas os faltantes
    manage.py reindexar_embeddings --tudo         # todos (forçado)
    manage.py reindexar_embeddings --batch 50     # tamanho do lote
"""

from __future__ import annotations

import logging

from django.core.management.base import BaseCommand

from apps.acervo.models import Analise, Artigo
from apps.busca_semantica.embeddings import embed_texts, service_available
from apps.busca_semantica.tasks import _texto_analise, _texto_artigo

logger = logging.getLogger("busca_semantica")


class Command(BaseCommand):
    help = "Gera embeddings semânticos para Artigo e Analise."

    def add_arguments(self, parser):  # type: ignore[no-untyped-def]
        parser.add_argument(
            "--tudo",
            action="store_true",
            help="Regenera todos, inclusive os que já têm embedding.",
        )
        parser.add_argument(
            "--batch",
            type=int,
            default=32,
            help="Número de registros por lote (default: 32).",
        )

    def handle(self, *args, **options) -> None:  # type: ignore[no-untyped-def]
        if not service_available():
            self.stderr.write(self.style.ERROR(
                "Serviço de embeddings indisponível. Verifique se o container "
                "está rodando: docker compose --profile embeddings up -d embeddings"
            ))
            return

        forca_tudo = options["tudo"]
        batch = options["batch"]

        self._processar_artigos(forca_tudo, batch)
        self._processar_analises(forca_tudo, batch)

        self.stdout.write(self.style.SUCCESS("Reindexação concluída."))

    def _processar_artigos(self, forca_tudo: bool, batch: int) -> None:
        from datetime import UTC, datetime

        qs = Artigo.objects.all()
        if not forca_tudo:
            qs = qs.filter(embedding__isnull=True)

        total = qs.count()
        self.stdout.write(f"Artigos a processar: {total}")

        processados = erros = 0
        ids = list(qs.values_list("pk", flat=True))

        for i in range(0, len(ids), batch):
            lote_ids = ids[i : i + batch]
            lote = list(Artigo.objects.filter(pk__in=lote_ids))
            textos = [_texto_artigo(a) for a in lote]
            results = embed_texts([t if t.strip() else "vazio" for t in textos])

            now = datetime.now(tz=UTC)
            for artigo, texto, vec in zip(lote, textos, results):
                if vec is None or not texto.strip():
                    erros += 1
                    continue
                Artigo.objects.filter(pk=artigo.pk).update(
                    embedding=vec,
                    embedding_atualizado_em=now,
                )
                processados += 1

            self.stdout.write(f"  artigos {i + 1}–{min(i + batch, total)} / {total}", ending="\r")

        self.stdout.write(f"\n  ✓ {processados} artigos indexados, {erros} ignorados/falhos.")

    def _processar_analises(self, forca_tudo: bool, batch: int) -> None:
        from datetime import UTC, datetime

        qs = Analise.objects.all()
        if not forca_tudo:
            qs = qs.filter(embedding__isnull=True)

        total = qs.count()
        self.stdout.write(f"Análises a processar: {total}")

        processados = erros = 0
        ids = list(qs.values_list("pk", flat=True))

        for i in range(0, len(ids), batch):
            lote_ids = ids[i : i + batch]
            lote = list(
                Analise.objects.filter(pk__in=lote_ids).select_related("resenha")
            )

            textos_estruturais = [_texto_analise(a) for a in lote]
            textos_resenha = [
                (a.resenha.texto if getattr(a, "resenha", None) else "") for a in lote
            ]

            # Envia todos os textos num único lote para o serviço
            todos = textos_estruturais + textos_resenha
            results = embed_texts([t if t.strip() else "vazio" for t in todos])
            mid = len(lote)

            now = datetime.now(tz=UTC)
            for j, analise in enumerate(lote):
                vec_est = results[j]
                vec_res = results[mid + j]
                updates: dict = {"embedding_atualizado_em": now}

                if vec_est and textos_estruturais[j].strip():
                    updates["embedding"] = vec_est
                    processados += 1
                else:
                    erros += 1

                if vec_res and textos_resenha[j].strip():
                    updates["embedding_resenha"] = vec_res

                Analise.objects.filter(pk=analise.pk).update(**updates)

            self.stdout.write(f"  análises {i + 1}–{min(i + batch, total)} / {total}", ending="\r")

        self.stdout.write(f"\n  ✓ {processados} análises indexadas, {erros} ignoradas/falhas.")
