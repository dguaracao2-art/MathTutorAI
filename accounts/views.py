from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse

from .forms import StudentRegistrationForm
from django.views.decorators.cache import never_cache


@never_cache
@login_required
def home(request):
    return render(request, "accounts/home.html")


@never_cache
def register(request):
    if request.user.is_authenticated:
        return redirect("accounts:home")
    form = StudentRegistrationForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        user = form.save(commit=False)
        user.is_staff = False
        user.is_superuser = False
        user.save()
        return redirect(reverse("accounts:login") + "?registered=1")
    return render(request, "accounts/register.html", {"form": form})
