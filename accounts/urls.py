from django.contrib.auth.views import LoginView, LogoutView
from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("crear-cuenta/", views.register, name="register"),
    path("", views.home, name="home"),
    path(
        "iniciar-sesion/",
        LoginView.as_view(
            template_name="accounts/login.html",
            redirect_authenticated_user=True,
        ),
        name="login",
    ),
    path("cerrar-sesion/", LogoutView.as_view(), name="logout"),
]
