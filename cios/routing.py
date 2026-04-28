from django.urls import re_path

from .consumers import CioEventConsumer, CioRequestConsumer


websocket_urlpatterns = [
    re_path(r"ws/cios/requests/$", CioRequestConsumer.as_asgi()),
    re_path(r"ws/cios/(?P<cio_id>\d+)/events/$", CioEventConsumer.as_asgi()),
]
