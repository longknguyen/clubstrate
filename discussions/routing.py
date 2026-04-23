from django.urls import re_path

from .consumers import DiscussionConsumer


websocket_urlpatterns = [
    re_path(r"ws/cios/(?P<cio_id>\d+)/discussions/$", DiscussionConsumer.as_asgi()),
]
