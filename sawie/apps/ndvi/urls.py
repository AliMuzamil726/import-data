from django.urls import path

from . import views

app_name = "ndvi"

urlpatterns = [
    path("", views.NDVIListView.as_view(), name="list"),
    path("upload/", views.ndvi_upload, name="upload"),
    path("<int:pk>/", views.NDVIDetailView.as_view(), name="detail"),
    path("<int:pk>/reprocess/", views.ndvi_reprocess, name="reprocess"),
    path("<int:pk>/delete/", views.ndvi_delete, name="delete"),
    path("export/<str:fmt>/", views.ndvi_export, name="export"),
]
