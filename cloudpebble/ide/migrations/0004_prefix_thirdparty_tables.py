from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('ide', '0003_alter_project_project_dependencies_and_more'),
    ]

    operations = [
        migrations.RunSQL(
            sql='ALTER TABLE social_auth_usersocialauth RENAME TO cloudpebble_social_auth_usersocialauth',
            reverse_sql='ALTER TABLE cloudpebble_social_auth_usersocialauth RENAME TO social_auth_usersocialauth',
        ),
        migrations.RunSQL(
            sql='ALTER TABLE social_auth_nonce RENAME TO cloudpebble_social_auth_nonce',
            reverse_sql='ALTER TABLE cloudpebble_social_auth_nonce RENAME TO social_auth_nonce',
        ),
        migrations.RunSQL(
            sql='ALTER TABLE social_auth_association RENAME TO cloudpebble_social_auth_association',
            reverse_sql='ALTER TABLE cloudpebble_social_auth_association RENAME TO social_auth_association',
        ),
        migrations.RunSQL(
            sql='ALTER TABLE social_auth_code RENAME TO cloudpebble_social_auth_code',
            reverse_sql='ALTER TABLE cloudpebble_social_auth_code RENAME TO social_auth_code',
        ),
        migrations.RunSQL(
            sql='ALTER TABLE social_auth_partial RENAME TO cloudpebble_social_auth_partial',
            reverse_sql='ALTER TABLE cloudpebble_social_auth_partial RENAME TO social_auth_partial',
        ),
        migrations.RunSQL(
            sql='ALTER TABLE registration_registrationprofile RENAME TO cloudpebble_registration_registrationprofile',
            reverse_sql='ALTER TABLE cloudpebble_registration_registrationprofile RENAME TO registration_registrationprofile',
        ),
        migrations.RunSQL(
            sql='ALTER TABLE registration_supervisedregistrationprofile RENAME TO cloudpebble_registration_supervisedregistrationprofile',
            reverse_sql='ALTER TABLE cloudpebble_registration_supervisedregistrationprofile RENAME TO registration_supervisedregistrationprofile',
        ),
    ]
