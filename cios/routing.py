from django.urls import re_path

from .consumers import CioRequestConsumer


websocket_urlpatterns = [
    re_path(r"ws/cios/requests/$", CioRequestConsumer.as_asgi()),
]
