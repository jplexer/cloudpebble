# Generated manually for alloy project type

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ide', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='project',
            name='project_type',
            field=models.CharField(
                choices=[
                    ('native', 'Pebble C SDK'),
                    ('simplyjs', 'Simply.js'),
                    ('pebblejs', 'Pebble.js (beta)'),
                    ('package', 'Pebble Package'),
                    ('rocky', 'Rocky.js'),
                    ('alloy', 'Alloy (beta)'),
                ],
                default='native',
                max_length=10,
            ),
        ),
        migrations.AlterField(
            model_name='sourcefile',
            name='target',
            field=models.CharField(
                choices=[
                    ('app', 'App'),
                    ('pkjs', 'PebbleKit JS'),
                    ('worker', 'Worker'),
                    ('public', 'Public Header File'),
                    ('common', 'Shared JS'),
                    ('embeddedjs', 'Embedded JS'),
                ],
                default='app',
                max_length=12,
            ),
        ),
    ]
