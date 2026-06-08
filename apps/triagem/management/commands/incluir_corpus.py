"""Inclui no corpus **todos** os registros de um projeto ANCO (sem triagem).

Põe todo registro não-legado em `INCLUIDO` + promove ao acervo: identificados
pendentes e também os que foram excluídos na autotriagem antiga (tratada como
obsoleta). Idempotente: rodar de novo não duplica.

Exemplo:
    python manage.py incluir_corpus --projeto analise-cognitiva
    python manage.py incluir_corpus --projeto analise-cognitiva --dry-run
"""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from apps.triagem.aprovacao import incluir_corpus_total
from apps.triagem.models import ProtocoloTriagem, RegistroTriagem


class Command(BaseCommand):
    help = "Inclui no corpus todos os registros de um projeto ANCO (sem triagem prévia)."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--projeto", type=str, default=None, help="Slug do projeto (default: projeto ativo)."
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Só conta quantos entrariam no corpus, sem alterar nada.",
        )

    def handle(self, *args, **opts) -> None:
        if opts["projeto"]:
            projeto = ProtocoloTriagem.objects.filter(slug=opts["projeto"]).first()
            if projeto is None:
                raise CommandError(f"Projeto '{opts['projeto']}' não encontrado.")
        else:
            projeto = ProtocoloTriagem.ativo()

        if not projeto.eh_anco:
            raise CommandError(
                f"Projeto '{projeto.slug}' não está no modo ANCO — sem inclusão automática."
            )

        _St = RegistroTriagem.Status
        pendentes = projeto.registros.filter(
            status__in=(_St.IDENTIFICADO, _St.EXCLUIDO), ja_no_acervo=False
        ).count()

        if opts["dry_run"]:
            self.stdout.write(
                self.style.WARNING(
                    f"[dry-run] Projeto '{projeto.slug}': {pendentes} registro(s) entrariam no corpus."
                )
            )
            return

        n = incluir_corpus_total(projeto)
        self.stdout.write(
            self.style.SUCCESS(f"Projeto '{projeto.slug}': {n} registro(s) incluído(s) no corpus.")
        )
