from django.urls import path

from . import views

app_name = "farmers"

urlpatterns = [
    path("", views.FarmerListView.as_view(), name="list"),
    path("add/", views.farmer_create, name="create"),
    path("<int:pk>/", views.FarmerDetailView.as_view(), name="detail"),
    path("<int:pk>/edit/", views.farmer_update, name="update"),
    path("<int:pk>/delete/", views.farmer_delete, name="delete"),
    path("export/<str:fmt>/", views.farmer_export, name="export"),
]
