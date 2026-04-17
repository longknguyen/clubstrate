from django.urls import path

from discussions import views
from cios import views as cio_views

app_name = 'discussions'
urlpatterns = [
    path('cio/<int:cio_id>/post/create/', views.create_post, name='create_post'),
    path('post/<int:post_id>/comment/', views.create_comment, name='create_comment'),
    path('post/<int:post_id>/like/', views.toggle_post_like, name='toggle_post_like'),
    path('comments/<int:comment_id>/like/', views.toggle_comment_like, name='toggle_comment_like'),
    path('<int:cio_id>/', views.discussion_list, name='list'),
    path('cio/<int:cio_id>/edit/', cio_views.edit_cio_about, name='edit_cio_about'),
]