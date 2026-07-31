from django.urls import path

from . import views

app_name = "crops"

urlpatterns = [
    path("", views.CropListView.as_view(), name="list"),
    path("add/", views.crop_create, name="create"),
    path("<int:pk>/", views.CropDetailView.as_view(), name="detail"),
    path("<int:pk>/edit/", views.crop_update, name="update"),
    path("<int:pk>/delete/", views.crop_delete, name="delete"),
    path("export/<str:fmt>/", views.crop_export, name="export"),
]
