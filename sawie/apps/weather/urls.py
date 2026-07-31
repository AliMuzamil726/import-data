from django.urls import path

from . import views

app_name = "weather"

urlpatterns = [
    path("", views.weather_index, name="index"),
    path("api/field/<int:pk>/", views.weather_api, name="api"),
    path("export/<str:fmt>/", views.weather_export, name="export"),
]
