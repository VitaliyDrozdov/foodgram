# Generated by Django 4.2.11 on 2024-05-16 18:24

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('recipe', '0004_remove_link_short_link_link_short_code'),
    ]

    operations = [
        migrations.AlterField(
            model_name='link',
            name='original_link',
            field=models.URLField(blank=True),
        ),
    ]
