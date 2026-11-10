"""Rutas de la API REST. La web conserva las suyas en tutoring/urls.py."""
from django.urls import path

from . import api_views

app_name = "api"

urlpatterns = [
    path("lecturas/", api_views.LecturaAPIView.as_view(), name="lecturas"),
    path("revisiones/", api_views.RevisionAPIView.as_view(), name="revisiones"),
    path("pistas/", api_views.PistaAPIView.as_view(), name="pistas"),
]
