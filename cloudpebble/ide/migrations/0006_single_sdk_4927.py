from django.db import migrations, models


def migrate_all_projects_to_4927(apps, schema_editor):
    Project = apps.get_model('ide', 'Project')
    Project.objects.exclude(sdk_version='4.9.127').update(sdk_version='4.9.127')


class Migration(migrations.Migration):
    dependencies = [
        ('ide', '0005_multi_sdk_version'),
    ]

    operations = [
        migrations.RunPython(migrate_all_projects_to_4927, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='project',
            name='sdk_version',
            field=models.CharField(
                choices=[('4.9.127', 'SDK 4.9.127')],
                default='4.9.127',
                max_length=32,
            ),
        ),
    ]
