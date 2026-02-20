from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):
    dependencies = [
        ('ide', '0006_single_sdk_4927'),
    ]

    operations = [
        migrations.CreateModel(
            name='UserGithubRepoSync',
            fields=[
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, primary_key=True, related_name='github_repo_sync', serialize=False, to=settings.AUTH_USER_MODEL)),
                ('token', models.CharField(blank=True, max_length=50, null=True)),
                ('nonce', models.CharField(blank=True, max_length=36, null=True)),
                ('username', models.CharField(blank=True, max_length=50, null=True)),
                ('avatar', models.CharField(blank=True, max_length=255, null=True)),
            ],
            options={
                'db_table': 'cloudpebble_user_github_repo_sync',
            },
        ),
    ]
