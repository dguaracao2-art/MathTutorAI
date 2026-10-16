from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.views.decorators.cache import never_cache

from .models import Exercise


@never_cache
@login_required
def exercise_list(request):
    exercises = Exercise.objects.filter(is_active=True)

    return render(
        request,
        "tutoring/exercise_list.html",
        {"exercises": exercises},
    )