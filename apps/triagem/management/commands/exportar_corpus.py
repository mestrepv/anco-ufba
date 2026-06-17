"""Exporta o corpus de um projeto PRISMA-ScR em CSV (formato ASReview).

Uso:
    manage.py exportar_corpus <slug> [--saida arquivo.csv]

Colunas compatíveis com o ASReview LAB: `anco_id`, `title`, `abstract`,
`authors`, `year`, `doi`, `keywords`, `journal`, `label_included`
(1=incluído, 0=excluído, vazio=ainda sem decisão — útil como *prior knowledge*
ou para avaliar recall). Duplicatas são omitidas.

Parte do piloto do ASReview — ver `docs/planos/integracao-asreview.md`.
"""

from __future__ import annotations

import contextlib
import csv
import sys

from django.core.management.base import BaseCommand, CommandError

from apps.triagem.models import ProtocoloTriagem, RegistroTriagem

_S = RegistroTriagem.Status
_LABEL = {
    _S.INCLUIDO: "1",
    _S.INCLUIDO_TA: "1",
    _S.EXCLUIDO: "0",
    _S.EXCLUIDO_TC: "0",
}


class Command(BaseCommand):
    help = "Exporta o corpus de um projeto PRISMA em CSV (formato ASReview)."

    def add_arguments(self, parser) -> None:
        parser.add_argument("slug", help="slug do projeto da triagem")
        parser.add_argument("--saida", help="arquivo de saída (default: stdout)")

    def handle(self, *args, **opts) -> None:
        projeto = ProtocoloTriagem.objects.filter(slug=opts["slug"]).first()
        if projeto is None:
            raise CommandError(f"Projeto {opts['slug']!r} não encontrado.")

        regs = projeto.registros.exclude(status=_S.DUPLICADO).order_by("pk")
        if opts["saida"]:
            cm = open(opts["saida"], "w", newline="", encoding="utf-8")  # noqa: SIM115 (fechado no `with`)
        else:
            cm = contextlib.nullcontext(sys.stdout)
        n = 0
        with cm as saida:
            w = csv.writer(saida)
            # `anco_id` (nao `record_id`): `record_id` e um nome reservado do
            # ASReview LAB (ele gera o proprio) e colide no type casting. Mantemos
            # nosso pk como `anco_id` p/ reimportar os rotulos depois.
            w.writerow(
                [
                    "anco_id", "title", "abstract", "authors", "year",
                    "doi", "keywords", "journal", "label_included",
                ]
            )
            for r in regs.iterator():
                w.writerow(
                    [
                        r.pk, r.titulo, r.resumo, r.autores, r.ano or "",
                        r.doi, r.palavras_chaves, r.titulo_periodico, _LABEL.get(r.status, ""),
                    ]
                )
                n += 1
        self.stderr.write(
            self.style.SUCCESS(f"{n} registro(s) de {projeto.slug} exportado(s).")
        )
