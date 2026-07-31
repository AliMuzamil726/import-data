from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("notifications/", views.notification_list, name="notifications"),
    path("notifications/feed/", views.notification_feed, name="notification_feed"),
    path("notifications/read/", views.notification_mark_read, name="notification_read"),
]
