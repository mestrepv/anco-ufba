"""
Mapeia valores legados de `Artigo.area` (texto livre) para as grandes áreas
do CNPq/CAPES, onde o enquadramento é óbvio. Valores ambíguos são mantidos
como estão (reportados no log). Idempotente.
"""

from django.db import migrations

# valor legado -> grande área (CNPq/CAPES)
MAPA = {
    # Ciências Humanas
    "Psicologia": "Ciências Humanas",
    "Psicologia da Educação": "Ciências Humanas",
    "Psicologia Social": "Ciências Humanas",
    "Psicologia social": "Ciências Humanas",
    "Psicologia Infantil": "Ciências Humanas",
    "Psicologia e Educação": "Ciências Humanas",
    "Educação": "Ciências Humanas",
    "Avaliação Educacional": "Ciências Humanas",
    "Sociologia": "Ciências Humanas",
    "Ciências Políticas e Sociais": "Ciências Humanas",
    # Linguística, Letras e Artes
    "Letras": "Linguística, Letras e Artes",
    "Linguística/Literatura": "Linguística, Letras e Artes",
    # Ciências Biológicas
    "Bioquimica": "Ciências Biológicas",
    "Neurociência cognitiva": "Ciências Biológicas",
    # Ciências da Saúde
    "Saúde": "Ciências da Saúde",
    "Medicina-Neurologia": "Ciências da Saúde",
    "Psiquiatria": "Ciências da Saúde",
    # Engenharias
    "Engenharia Biomédica": "Engenharias",
    "Engenharia e Segurança de Sistemas": "Engenharias",
    "Engenharia Cognitiva/Ergonomia": "Engenharias",
    "Engineering, Water Management": "Engenharias",
    "Recursos Hídricos": "Engenharias",
    # Multidisciplinar (cruzam áreas ou são "Ensino de …")
    "Psicologia/Economia": "Multidisciplinar",
    "Educação Matemática": "Multidisciplinar",
    "Educação/Matemática": "Multidisciplinar",
    "Educação e Engenharia": "Multidisciplinar",
    "Educação/Linguística": "Multidisciplinar",
    "Comunicação e Linguagem": "Multidisciplinar",
    "Ensino de Física": "Multidisciplinar",
    "Ecologia e Saúde": "Multidisciplinar",
    # Ciências Sociais Aplicadas
    "Ciência Administrativa": "Ciências Sociais Aplicadas",
    "Ciência da Informação": "Ciências Sociais Aplicadas",
    # demais enquadráveis
    "Cognition and Neuroscience": "Ciências Biológicas",
    "Psicologia do Esporte": "Ciências Humanas",
    "Relações Pessoais e Sociais": "Ciências Humanas",
    "Biocibernetica": "Multidisciplinar",
    "Educação/Política Pública": "Multidisciplinar",
    "Educação/Psicologia": "Multidisciplinar",
    "Psicologia/Linguística": "Multidisciplinar",
    # mantidos como estão (vagos demais): "Geral", "Segurança"
}

GRANDES_AREAS = {
    "Ciências Exatas e da Terra", "Ciências Biológicas", "Engenharias",
    "Ciências da Saúde", "Ciências Agrárias", "Ciências Sociais Aplicadas",
    "Ciências Humanas", "Linguística, Letras e Artes", "Multidisciplinar",
    "Outros",
}


def mapear(apps, schema_editor):
    Artigo = apps.get_model("acervo", "Artigo")
    total = 0
    for legado, grande in MAPA.items():
        n = Artigo.objects.filter(area=legado).update(area=grande)
        total += n
    # Reporta o que sobrou fora das grandes áreas (não mapeado).
    nao_mapeados = sorted(
        set(
            Artigo.objects.exclude(area="")
            .exclude(area__in=GRANDES_AREAS)
            .values_list("area", flat=True)
        )
    )
    print(f"\n  [mapear_areas] registros remapeados={total} "
          f"| valores ainda fora das grandes áreas (mantidos): {nao_mapeados}")


def reverter(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [("acervo", "0012_alter_artigo_area")]
    operations = [migrations.RunPython(mapear, reverter)]
