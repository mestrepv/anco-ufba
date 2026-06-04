"""
Padroniza a grafia de duas bases: Scielo -> SciELO, Rianco -> RIAnCo.
Renomeia in-place (mantém o PK; FKs de Artigo seguem o termo). Idempotente.
"""

from django.db import migrations

RENOMEAR = {"Scielo": "SciELO", "Rianco": "RIAnCo"}


def aplicar(apps, schema_editor):
    Termo = apps.get_model("vocabulario", "TermoVocabulario")
    for antigo, novo in RENOMEAR.items():
        Termo.objects.filter(vocabulario__codigo="base", nome=antigo).update(nome=novo)


def reverter(apps, schema_editor):
    Termo = apps.get_model("vocabulario", "TermoVocabulario")
    for antigo, novo in RENOMEAR.items():
        Termo.objects.filter(vocabulario__codigo="base", nome=novo).update(nome=antigo)


class Migration(migrations.Migration):
    dependencies = [("vocabulario", "0002_bases_consulta_adicionais")]
    operations = [migrations.RunPython(aplicar, reverter)]
