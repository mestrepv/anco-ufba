"""Migration inicial do app publico — habilita unaccent para FTS sem acentos."""

from django.contrib.postgres.operations import UnaccentExtension
from django.db import migrations


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        UnaccentExtension(),
    ]
