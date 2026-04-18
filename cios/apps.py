from django.apps import AppConfig


class CiosConfig(AppConfig):
    name = 'cios'

    def ready(self):
        import cios.admin