"""
Migração de dados para o novo fluxo (revisão só para resenhas; curadoria publica).

- Cria uma Resenha a partir de cada Analise com `resenha_critica` não-vazia,
  herdando a visibilidade da análise (legado/publicada → resenha publicada;
  demais → rascunho).
- Move análises presas em `em_revisao` (fluxo antigo) de volta para `submetida`
  (aguardando curadoria).
- Descarta as revisões estruturais antigas; religa revisões cegas à Resenha
  correspondente e descarta as cegas órfãs (análise sem resenha).

Idempotente: re-rodar não duplica. Reverso = noop (não recria dados antigos).
"""

from django.db import migrations


def migrar(apps, schema_editor):
    Analise = apps.get_model("acervo", "Analise")
    Resenha = apps.get_model("acervo", "Resenha")
    Revisao = apps.get_model("acervo", "Revisao")

    # (a) Cria Resenha a partir de resenha_critica não-vazia (idempotente).
    criadas = 0
    for analise in Analise.objects.exclude(resenha_critica="").exclude(
        resenha_critica__isnull=True
    ):
        if Resenha.objects.filter(analise=analise).exists():
            continue
        if analise.status == "legado":
            status = "legado"
            publicada_em = analise.publicada_em or analise.criado_em
        elif analise.status == "publicada":
            status = "publicada"
            publicada_em = analise.publicada_em
        else:
            status = "rascunho"
            publicada_em = None
        Resenha.objects.create(
            analise=analise,
            texto=analise.resenha_critica,
            status=status,
            publicada_em=publicada_em,
        )
        criadas += 1

    # (b) Análises em revisão (fluxo antigo) voltam para a fila da curadoria.
    em_revisao = Analise.objects.filter(status="em_revisao").update(
        status="submetida"
    )
    # Análises 'aprovada' do fluxo antigo (se houver) também viram submetidas.
    aprovada = Analise.objects.filter(status="aprovada").update(status="submetida")

    # (c) Revisões estruturais antigas são descartadas.
    estruturais, _ = Revisao.objects.filter(tipo="estrutural").delete()

    # Revisões cegas: religa à Resenha da análise; órfãs (sem resenha) saem.
    religadas = 0
    orfas = 0
    for rev in Revisao.objects.filter(tipo="cega", resenha__isnull=True):
        resenha = Resenha.objects.filter(analise_id=rev.analise_id).first()
        if resenha:
            rev.resenha = resenha
            rev.save(update_fields=["resenha"])
            religadas += 1
        else:
            rev.delete()
            orfas += 1

    print(
        f"\n  [migrar_resenhas] resenhas criadas={criadas} "
        f"em_revisao->submetida={em_revisao} aprovada->submetida={aprovada} "
        f"revisoes_estruturais_apagadas={estruturais} "
        f"cegas_religadas={religadas} cegas_orfas_apagadas={orfas}"
    )


def reverter(apps, schema_editor):
    # Sem reversão de dados: o fluxo antigo não é reconstruído.
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("acervo", "0008_analise_aprovada_em_analise_aprovada_por_and_more"),
    ]

    operations = [
        migrations.RunPython(migrar, reverter),
    ]
