"""
Cria/atualiza os schedules do django-q2 da plataforma.

Idempotente: roda quantas vezes quiser.

Schedules:
- task_verificar_prazos  (diario)  — re-sorteia revisoes expiradas
- task_verificar_links   (semanal) — checa link_acesso dos artigos publicados
"""

from __future__ import annotations

from django.core.management.base import BaseCommand
from django.utils import timezone
from django_q.models import Schedule

SCHEDULES = [
    {
        "name": "verificar_prazos_revisao",
        "func": "apps.acervo.tasks.task_verificar_prazos",
        "schedule_type": Schedule.DAILY,
    },
    {
        "name": "verificar_saude_dos_links",
        "func": "apps.acervo.tasks.task_verificar_links",
        "schedule_type": Schedule.WEEKLY,
    },
]


class Command(BaseCommand):
    help = "Cria/atualiza schedules do django-q2 (idempotente)."

    def handle(self, *args, **options):
        agora = timezone.now()
        criados = atualizados = 0
        for s in SCHEDULES:
            obj, criado = Schedule.objects.update_or_create(
                name=s["name"],
                defaults={
                    "func": s["func"],
                    "schedule_type": s["schedule_type"],
                    "next_run": agora,
                    "repeats": -1,
                },
            )
            if criado:
                criados += 1
                self.stdout.write(self.style.SUCCESS(f"+ {obj.name} ({s['schedule_type']})"))
            else:
                atualizados += 1
                self.stdout.write(f"~ {obj.name} ({s['schedule_type']})")
        self.stdout.write(
            self.style.SUCCESS(f"\nOK — {criados} criados, {atualizados} atualizados.")
        )
