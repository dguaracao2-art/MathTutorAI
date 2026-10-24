from django.urls import path

from . import review_views, views

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
        path("confirmar/", views.confirm_sum, name="confirm_sum"),
    path("comprobar/", review_views.check_sum, name="check_sum"),
    path("resultado/", review_views.review_result, name="review_result"),
    path("pista/", review_views.show_hint, name="show_hint"),
    path("reintentar/", review_views.retry_sum, name="retry_sum"),
        
]
