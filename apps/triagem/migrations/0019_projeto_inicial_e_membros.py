"""Fase 12.0 — converte o protocolo existente no 'Projeto 1' e enrola a equipe.

Idempotente: roda 2x sem duplicar. Aditivo; não toca acervo/análise.
"""

from django.db import migrations
from django.utils.text import slugify

NOME_PADRAO = "Análise Cognitiva"
SLUG_PADRAO = "analise-cognitiva"


def frente(apps, schema_editor):
    Protocolo = apps.get_model("triagem", "ProtocoloTriagem")
    Membro = apps.get_model("triagem", "ProjetoMembro")
    User = apps.get_model("core", "User")

    protocolo = Protocolo.objects.order_by("id").first()
    if protocolo is None:
        return  # base vazia; nada a migrar

    campos = []
    if not protocolo.nome:
        protocolo.nome = NOME_PADRAO
        campos.append("nome")
    if not protocolo.slug:
        base = slugify(protocolo.nome) or SLUG_PADRAO
        slug = base
        i = 2
        while Protocolo.objects.exclude(pk=protocolo.pk).filter(slug=slug).exists():
            slug = f"{base}-{i}"
            i += 1
        protocolo.slug = slug
        campos.append("slug")
    if campos:
        protocolo.save(update_fields=campos)

    # Equipe atual = usuários ativos com papel analista/curador → membros do Projeto 1.
    for u in User.objects.filter(is_active=True, papel__in=["analista", "curador"]):
        papel = "curador" if u.papel == "curador" else "analista"
        Membro.objects.get_or_create(
            projeto=protocolo, usuario=u, defaults={"papel": papel}
        )


def tras(apps, schema_editor):
    Membro = apps.get_model("triagem", "ProjetoMembro")
    Membro.objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [
        ("triagem", "0018_protocolotriagem_arquivado_and_more"),
    ]

    operations = [
        migrations.RunPython(frente, tras),
    ]
