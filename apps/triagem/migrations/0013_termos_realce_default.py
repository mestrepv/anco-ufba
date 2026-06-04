"""Popula `termos_realce` do protocolo existente (idempotente)."""

from django.db import migrations

PADRAO = "análise cognitiva, cognitive analysis, cognitive analytics, cognição, cognition"


def preencher(apps, schema_editor):
    Protocolo = apps.get_model("triagem", "ProtocoloTriagem")
    Protocolo.objects.filter(termos_realce="").update(termos_realce=PADRAO)


def limpar(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [("triagem", "0012_protocolotriagem_termos_realce")]
    operations = [migrations.RunPython(preencher, limpar)]
