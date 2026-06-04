"""
Adiciona bases de consulta faltantes ao vocabulário `base`.
Idempotente (get_or_create por nome); não duplica as já existentes.
"""

from django.db import migrations

NOVAS_BASES = ["Rianco", "Saber Aberto", "Scielo"]


def adicionar(apps, schema_editor):
    Vocabulario = apps.get_model("vocabulario", "Vocabulario")
    Termo = apps.get_model("vocabulario", "TermoVocabulario")
    # Só anexa termos a um vocabulário `base` já existente (não o cria — o
    # seed do `base` vem da fixture/legado; criar aqui quebraria fixtures de
    # teste que criam o próprio `base`).
    base = Vocabulario.objects.filter(codigo="base").first()
    if base is None:
        return
    for nome in NOVAS_BASES:
        Termo.objects.get_or_create(
            vocabulario=base, nome=nome, defaults={"ativo": True}
        )


def remover(apps, schema_editor):
    # Remove só as que esta migração adicionou e que não têm artigos ligados.
    Termo = apps.get_model("vocabulario", "TermoVocabulario")
    Termo.objects.filter(
        vocabulario__codigo="base", nome__in=NOVAS_BASES, artigos_por_base__isnull=True
    ).delete()


class Migration(migrations.Migration):
    dependencies = [("vocabulario", "0001_initial")]
    operations = [migrations.RunPython(adicionar, remover)]
