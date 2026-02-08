from django.apps import AppConfig


class CloudPebbleAuthConfig(AppConfig):
    name = 'auth'
    label = 'cloudpebble_auth'  # Unique label to avoid conflict with django.contrib.auth
    verbose_name = 'CloudPebble Authentication'
