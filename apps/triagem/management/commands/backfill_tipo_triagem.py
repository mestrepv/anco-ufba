"""Preenche `RegistroTriagem.tipo` reparseando o arquivo guardado em cada Busca.

Útil para registros importados antes do campo `tipo` existir. Idempotente:
só preenche onde está vazio. Casa pelo identificador determinístico.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.triagem.importacao import chave_dedup, decodificar, parse_conteudo
from apps.triagem.models import Busca, RegistroTriagem


class Command(BaseCommand):
    help = "Backfill de RegistroTriagem.tipo a partir dos arquivos das buscas."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **opts) -> None:
        dry = opts["dry_run"]
        atualizados = 0
        for busca in Busca.objects.exclude(arquivo="").select_related("protocolo"):
            if not busca.formato or not busca.arquivo:
                continue
            try:
                conteudo = decodificar(busca.arquivo.read())
                registros = parse_conteudo(conteudo, busca.formato)
            except Exception as exc:  # noqa: BLE001
                self.stderr.write(f"Busca #{busca.pk}: falha ao reparsear ({exc})")
                continue

            for bruto in registros:
                tipo = (bruto.get("tipo") or "").strip()[:40]
                if not tipo:
                    continue
                ident = chave_dedup(
                    bruto.get("doi"), bruto.get("isbn"), bruto.get("titulo") or "",
                    bruto.get("ano"), bruto.get("titulo_periodico") or "",
                )
                reg = RegistroTriagem.objects.filter(
                    protocolo=busca.protocolo, identificador=ident, tipo=""
                ).first()
                if reg is None:
                    continue
                if not dry:
                    reg.tipo = tipo
                    reg.save(update_fields=["tipo"])
                atualizados += 1

        prefixo = "(dry-run) " if dry else ""
        self.stdout.write(self.style.SUCCESS(f"{prefixo}{atualizados} registro(s) atualizado(s)."))
