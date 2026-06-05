"""Recalcula `relevancia_score` dos registros (Revisão ANCO, Fase 13).

Uso:
    manage.py recalcular_relevancia                # todos os projetos
    manage.py recalcular_relevancia --projeto slug # um projeto
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.triagem.models import ProtocoloTriagem
from apps.triagem.relevancia import recalcular_protocolo


class Command(BaseCommand):
    help = "Recalcula o score de relevância (correspondência de termos) dos registros."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--projeto",
            dest="slug",
            default=None,
            help="Slug do projeto (omitido = todos).",
        )

    def handle(self, *args, **opts) -> None:
        qs = ProtocoloTriagem.objects.all()
        if opts["slug"]:
            qs = qs.filter(slug=opts["slug"])
            if not qs.exists():
                self.stderr.write(self.style.ERROR(f"Projeto '{opts['slug']}' não encontrado."))
                return
        total = 0
        for protocolo in qs:
            n = recalcular_protocolo(protocolo)
            total += n
            self.stdout.write(f"{protocolo.nome or protocolo.titulo}: {n} registros.")
        self.stdout.write(self.style.SUCCESS(f"Relevância recalculada para {total} registros."))
