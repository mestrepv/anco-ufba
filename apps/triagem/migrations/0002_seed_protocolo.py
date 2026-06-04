"""Seed do ProtocoloTriagem singleton (idempotente).

Cria o único protocolo da revisão de escopo da AnCo com critérios placeholder.
O curador edita os critérios no admin. Rodar 2x não duplica.
"""

from django.db import migrations

TITULO = "Revisão de escopo — Análise Cognitiva"
PERGUNTA = (
    "Quais estudos sobre Análise Cognitiva devem compor o acervo, segundo "
    "critérios de inclusão/exclusão pré-registrados?"
)
INCLUSAO = (
    "- Aborda Análise Cognitiva (ou correlatos) como objeto, método ou referencial.\n"
    "- Texto completo recuperável.\n"
    "- (demais critérios a definir pelo grupo)"
)
EXCLUSAO = (
    "- Fora do escopo da Análise Cognitiva.\n"
    "- Duplicado / sem texto completo.\n"
    "- (demais critérios a definir pelo grupo)"
)


def criar(apps, schema_editor):
    Protocolo = apps.get_model("triagem", "ProtocoloTriagem")
    if Protocolo.objects.exists():
        return
    Protocolo.objects.create(
        titulo=TITULO,
        pergunta_pesquisa=PERGUNTA,
        criterios_inclusao=INCLUSAO,
        criterios_exclusao=EXCLUSAO,
        n_revisores=2,
        prazo_dias=21,
    )


def remover(apps, schema_editor):
    # Remove só o protocolo-seed se ainda não tiver buscas/registros ligados.
    Protocolo = apps.get_model("triagem", "ProtocoloTriagem")
    Protocolo.objects.filter(
        titulo=TITULO, buscas__isnull=True, registros__isnull=True
    ).delete()


class Migration(migrations.Migration):
    dependencies = [("triagem", "0001_initial")]
    operations = [migrations.RunPython(criar, remover)]
