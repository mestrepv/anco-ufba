"""
Comando de backup do banco de dados (Fase 7).

Roda `pg_dump` para um arquivo `.dump` (custom format), comprimido,
nomeado com timestamp. Mantem retencao local configuravel via env
(default 7 dias). Sincronia com S3-compatible eh feita por script
externo (`infra/backup/sync_s3.sh`) — este comando so cria o dump.

Uso:
    python manage.py backup_db                 # dump no diretorio default
    python manage.py backup_db --output /tmp   # diretorio customizado
    python manage.py backup_db --no-prune      # nao apaga dumps antigos
"""

from __future__ import annotations

import os
import shutil
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Cria dump do banco com pg_dump (custom format, comprimido)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            default=None,
            help="Diretorio onde salvar o dump (default: BACKUP_DIR ou /var/backups/anco).",
        )
        parser.add_argument(
            "--retencao-dias",
            type=int,
            default=None,
            help="Mantem dumps dos ultimos N dias (default: BACKUP_RETENCAO_DIAS ou 7).",
        )
        parser.add_argument(
            "--no-prune",
            action="store_true",
            help="Nao remove dumps antigos.",
        )

    def handle(self, *args, **options):
        if shutil.which("pg_dump") is None:
            raise CommandError("pg_dump nao encontrado no PATH. Instale postgresql-client.")

        db = settings.DATABASES["default"]
        output_dir = Path(options["output"] or os.environ.get("BACKUP_DIR") or "/var/backups/anco")
        output_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
        nome = f"anco-{timestamp}.dump"
        destino = output_dir / nome

        env = {
            **os.environ,
            "PGPASSWORD": db.get("PASSWORD", "") or "",
        }

        cmd = [
            "pg_dump",
            "--host",
            db["HOST"],
            "--port",
            str(db["PORT"]),
            "--username",
            db["USER"],
            "--dbname",
            db["NAME"],
            "--format=custom",
            "--compress=9",
            "--no-owner",
            "--no-privileges",
            "--file",
            str(destino),
        ]
        self.stdout.write(f"Backup -> {destino}")
        try:
            subprocess.run(cmd, env=env, check=True, capture_output=True)
        except subprocess.CalledProcessError as exc:
            raise CommandError(
                f"pg_dump falhou: {exc.stderr.decode('utf-8', errors='replace')[:500]}"
            ) from exc

        tamanho = destino.stat().st_size
        self.stdout.write(self.style.SUCCESS(f"OK — {nome} ({tamanho / 1_000_000:.1f} MB)"))

        if not options["no_prune"]:
            self._prune(
                output_dir,
                dias=options["retencao_dias"] or int(os.environ.get("BACKUP_RETENCAO_DIAS", "7")),
            )

    def _prune(self, dir_: Path, dias: int) -> None:
        cutoff = datetime.now(tz=UTC) - timedelta(days=dias)
        removidos = 0
        for f in dir_.glob("anco-*.dump"):
            mtime = datetime.fromtimestamp(f.stat().st_mtime, tz=UTC)
            if mtime < cutoff:
                f.unlink()
                removidos += 1
        if removidos:
            self.stdout.write(f"Removidos {removidos} dumps com >{dias} dias.")
