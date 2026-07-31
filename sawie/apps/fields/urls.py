from django.urls import path

from . import views

app_name = "fields"

urlpatterns = [
    path("", views.FieldListView.as_view(), name="list"),
    path("add/", views.field_create, name="create"),
    path("map/", views.field_map, name="map"),
    path("map/data/", views.field_geojson, name="geojson"),
    path("<int:pk>/", views.FieldDetailView.as_view(), name="detail"),
    path("<int:pk>/edit/", views.field_update, name="update"),
    path("<int:pk>/delete/", views.field_delete, name="delete"),
    path("<int:pk>/boundary/", views.boundary_save, name="boundary_save"),
    path("<int:pk>/activities/add/", views.activity_create, name="activity_create"),
    path("activities/<int:pk>/delete/", views.activity_delete, name="activity_delete"),
    path("export/<str:fmt>/", views.field_export, name="export"),
]
