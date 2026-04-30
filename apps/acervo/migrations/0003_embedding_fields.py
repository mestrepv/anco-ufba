"""Adiciona campos de embedding (pgvector) a Artigo e Analise."""

import pgvector.django
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("acervo", "0002_initial"),
        ("busca_semantica", "0001_pgvector_extension"),
    ]

    operations = [
        # Artigo
        migrations.AddField(
            model_name="artigo",
            name="embedding",
            field=pgvector.django.VectorField(
                blank=True,
                dimensions=384,
                help_text="Embedding de titulo+resumo+palavras_chaves (Fase 8).",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="artigo",
            name="embedding_atualizado_em",
            field=models.DateTimeField(blank=True, null=True),
        ),
        # Analise
        migrations.AddField(
            model_name="analise",
            name="embedding",
            field=pgvector.django.VectorField(
                blank=True,
                dimensions=384,
                help_text="Embedding dos campos estruturais da análise (Fase 8).",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="analise",
            name="embedding_resenha",
            field=pgvector.django.VectorField(
                blank=True,
                dimensions=384,
                help_text="Embedding da resenha crítica, quando presente (Fase 8).",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="analise",
            name="embedding_atualizado_em",
            field=models.DateTimeField(blank=True, null=True),
        ),
        # Índices HNSW para busca por similaridade cosseno
        migrations.RunSQL(
            sql="""
                CREATE INDEX IF NOT EXISTS idx_artigo_embedding
                    ON acervo_artigo USING hnsw (embedding vector_cosine_ops)
                    WHERE embedding IS NOT NULL;

                CREATE INDEX IF NOT EXISTS idx_analise_embedding
                    ON acervo_analise USING hnsw (embedding vector_cosine_ops)
                    WHERE embedding IS NOT NULL;

                CREATE INDEX IF NOT EXISTS idx_analise_embedding_resenha
                    ON acervo_analise USING hnsw (embedding_resenha vector_cosine_ops)
                    WHERE embedding_resenha IS NOT NULL;
            """,
            reverse_sql="""
                DROP INDEX IF EXISTS idx_artigo_embedding;
                DROP INDEX IF EXISTS idx_analise_embedding;
                DROP INDEX IF EXISTS idx_analise_embedding_resenha;
            """,
        ),
    ]
