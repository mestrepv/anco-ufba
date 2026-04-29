"""Testes do comando backup_db (Fase 7)."""

from pathlib import Path
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

pytestmark = pytest.mark.django_db


class TestBackupDb:
    @patch("apps.core.management.commands.backup_db.shutil.which", return_value=None)
    def test_falha_se_pg_dump_ausente(self, _mock_which):
        with pytest.raises(CommandError, match="pg_dump"):
            call_command("backup_db", output="/tmp/test")

    @patch("apps.core.management.commands.backup_db.subprocess.run")
    @patch("apps.core.management.commands.backup_db.shutil.which", return_value="/usr/bin/pg_dump")
    def test_chama_pg_dump_com_args_esperados(self, _mock_which, mock_run, tmp_path: Path):
        # Simula sucesso: cria um arquivo no destino que o subprocess "criou"
        def fake_run(cmd, *args, **kwargs):
            destino = Path(cmd[cmd.index("--file") + 1])
            destino.write_bytes(b"dump-bytes" * 100)
            from subprocess import CompletedProcess

            return CompletedProcess(cmd, returncode=0, stdout=b"", stderr=b"")

        mock_run.side_effect = fake_run

        call_command("backup_db", output=str(tmp_path), no_prune=True)

        # Confirma que subprocess.run foi chamado com pg_dump
        assert mock_run.called
        cmd = mock_run.call_args.args[0]
        assert cmd[0] == "pg_dump"
        assert "--format=custom" in cmd
        assert "--compress=9" in cmd
        # Arquivo de dump foi criado
        dumps = list(tmp_path.glob("anco-*.dump"))
        assert len(dumps) == 1

    @patch("apps.core.management.commands.backup_db.subprocess.run")
    @patch("apps.core.management.commands.backup_db.shutil.which", return_value="/usr/bin/pg_dump")
    def test_prune_remove_dumps_antigos(self, _mock_which, mock_run, tmp_path: Path):
        # Cria um dump antigo (10 dias atras)
        antigo = tmp_path / "anco-20240101T000000Z.dump"
        antigo.write_bytes(b"old")
        import os
        import time

        ago = time.time() - 10 * 86400
        os.utime(antigo, (ago, ago))

        # Simula novo dump
        def fake_run(cmd, *args, **kwargs):
            destino = Path(cmd[cmd.index("--file") + 1])
            destino.write_bytes(b"new")
            from subprocess import CompletedProcess

            return CompletedProcess(cmd, returncode=0, stdout=b"", stderr=b"")

        mock_run.side_effect = fake_run

        call_command("backup_db", output=str(tmp_path), retencao_dias=7)

        # Antigo removido
        assert not antigo.exists()
        # Novo presente
        novos = list(tmp_path.glob("anco-*.dump"))
        assert len(novos) == 1
