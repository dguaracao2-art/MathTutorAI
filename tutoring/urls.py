from django.urls import path

from . import views

app_name = "tutoring"

urlpatterns = [
    path("", views.exercise_list, name="exercise_list"),
    path(
        "elegir/<int:pk>/",
        views.select_exercise,
        name="select_exercise",
    ),
    path(
        "ejercicio/",
        views.exercise_detail,
        name="exercise_detail",
    ),
    path(
        "fotografia/",
        views.upload_photo,
        name="upload_photo",
    ),
]