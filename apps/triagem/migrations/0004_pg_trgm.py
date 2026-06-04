"""Habilita a extensão pg_trgm (similaridade de título p/ possíveis duplicatas)."""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("triagem", "0003_busca_importado_em_busca_n_duplicados_and_more")]

    operations = [
        migrations.RunSQL(
            sql="CREATE EXTENSION IF NOT EXISTS pg_trgm;",
            reverse_sql="DROP EXTENSION IF EXISTS pg_trgm;",
        ),
    ]
