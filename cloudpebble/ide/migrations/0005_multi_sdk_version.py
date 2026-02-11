from django.db import migrations, models


def migrate_sdk_versions(apps, schema_editor):
    Project = apps.get_model('ide', 'Project')
    # Upgrade all old SDK version values to the new default
    Project.objects.filter(sdk_version='3').update(sdk_version='4.9.121-1-moddable')
    Project.objects.filter(sdk_version='2').update(sdk_version='4.9.121-1-moddable')


def reverse_sdk_versions(apps, schema_editor):
    Project = apps.get_model('ide', 'Project')
    Project.objects.filter(sdk_version='4.9.121-1-moddable').update(sdk_version='3')
    Project.objects.filter(sdk_version='4.9.77').update(sdk_version='3')


class Migration(migrations.Migration):

    dependencies = [
        ('ide', '0004_prefix_thirdparty_tables'),
    ]

    operations = [
        migrations.AlterField(
            model_name='project',
            name='sdk_version',
            field=models.CharField(
                choices=[
                    ('4.9.121-1-moddable', 'SDK 4.9.121 (Moddable)'),
                    ('4.9.77', 'SDK 4.9.77'),
                ],
                default='4.9.121-1-moddable',
                max_length=32,
            ),
        ),
        migrations.RunPython(migrate_sdk_versions, reverse_sdk_versions),
    ]
