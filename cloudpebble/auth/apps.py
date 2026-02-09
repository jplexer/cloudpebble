from django.apps import AppConfig


class CloudPebbleAuthConfig(AppConfig):
    name = 'auth'
    label = 'cloudpebble_auth'  # Unique label to avoid conflict with django.contrib.auth
    verbose_name = 'CloudPebble Authentication'

    def ready(self):
        from social_django.models import UserSocialAuth, Nonce, Association, Code, Partial
        for model in [UserSocialAuth, Nonce, Association, Code, Partial]:
            model._meta.db_table = 'cloudpebble_' + model._meta.db_table

        from registration.models import RegistrationProfile, SupervisedRegistrationProfile
        for model in [RegistrationProfile, SupervisedRegistrationProfile]:
            model._meta.db_table = 'cloudpebble_' + model._meta.db_table
