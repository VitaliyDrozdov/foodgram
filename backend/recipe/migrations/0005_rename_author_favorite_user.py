# Generated by Django 4.2.11 on 2024-05-10 20:12

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('recipe', '0004_alter_recipeingredient_ingredient'),
    ]

    operations = [
        migrations.RenameField(
            model_name='favorite',
            old_name='author',
            new_name='user',
        ),
    ]