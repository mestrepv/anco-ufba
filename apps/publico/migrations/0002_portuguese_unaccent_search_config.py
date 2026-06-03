"""Cria a text search configuration `portuguese_unaccent`.

A extensão `unaccent` (migração 0001) sozinha não afeta `to_tsvector('portuguese', ...)`.
Para que a busca textual ignore acentos, é preciso uma configuração que aplique
`unaccent` antes do stemmer português no pipeline de mapeamento de tokens.
"""

from django.db import migrations


CREATE_SQL = """
CREATE TEXT SEARCH CONFIGURATION portuguese_unaccent (COPY = portuguese);
ALTER TEXT SEARCH CONFIGURATION portuguese_unaccent
    ALTER MAPPING FOR hword, hword_part, word
    WITH unaccent, portuguese_stem;
"""

DROP_SQL = "DROP TEXT SEARCH CONFIGURATION IF EXISTS portuguese_unaccent;"


class Migration(migrations.Migration):
    dependencies = [
        ("publico", "0001_initial"),
    ]

    operations = [
        migrations.RunSQL(sql=CREATE_SQL, reverse_sql=DROP_SQL),
    ]
