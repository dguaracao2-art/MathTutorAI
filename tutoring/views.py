from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from .models import Exercise
from django.http import JsonResponse

from .forms import PhotoUploadForm, SumConfirmationForm


@never_cache
@login_required
def exercise_list(request):
    exercises = Exercise.objects.filter(is_active=True)

    return render(
        request,
        "tutoring/exercise_list.html",
        {"exercises": exercises},
    )


@never_cache
@login_required(redirect_field_name=None)
@require_POST
def select_exercise(request, pk):
    exercise = Exercise.objects.filter(
        pk=pk,
        is_active=True,
    ).first()

    if exercise is None:
        messages.info(
            request,
            "Esta suma ya no está disponible. Elige otra.",
        )
        return redirect("tutoring:exercise_list")
    request.session.pop("confirmed_sum", None)
    request.session["selected_exercise"] = {
        "id": exercise.pk,
        "operand_a": exercise.operand_a,
        "operand_b": exercise.operand_b,
    }

    return redirect("tutoring:exercise_detail")


@never_cache
@login_required
def exercise_detail(request):
    selected = request.session.get("selected_exercise")

    if not selected:
        return redirect("tutoring:exercise_list")

    exercise = Exercise.objects.filter(
        pk=selected["id"],
        operand_a=selected["operand_a"],
        operand_b=selected["operand_b"],
        is_active=True,
    ).first()

    if exercise is None:
        request.session.pop("selected_exercise", None)
        messages.info(
            request,
            "La suma elegida cambió o ya no está disponible. Elige otra.",
        )
        return redirect("tutoring:exercise_list")

    return render(
        request,
        "tutoring/exercise_detail.html",
        {
            "exercise": exercise,
            "confirmation_form": SumConfirmationForm()
        },
    )

@never_cache
@require_POST
def upload_photo(request):
    if not request.user.is_authenticated:
        return JsonResponse(
            {"error": "Tu sesión terminó. Vuelve a iniciar sesión."},
            status=401,
        )

    selected = request.session.get("selected_exercise")

    if not selected:
        return JsonResponse(
            {"error": "Primero elige una suma desde el banco."},
            status=409,
        )

    exercise = Exercise.objects.filter(
        pk=selected["id"],
        operand_a=selected["operand_a"],
        operand_b=selected["operand_b"],
        is_active=True,
    ).first()

    if (
        exercise is None
        or request.POST.get("exercise_id") != str(exercise.pk)
    ):
        return JsonResponse(
            {
                "error": (
                    "La suma cambió o ya no está disponible. "
                    "Vuelve al banco y elígela nuevamente."
                )
            },
            status=409,
        )
    request.session.pop("confirmed_sum", None)
    form = PhotoUploadForm(request.POST, request.FILES)

    if not form.is_valid():
        return JsonResponse(
            {"error": form.errors["photo"][0]},
            status=400,
        )

    return JsonResponse({"ok": True})

@never_cache
@require_POST
def confirm_sum(request):
    if not request.user.is_authenticated:
        return JsonResponse(
            {"error": "Tu sesión terminó. Vuelve a iniciar sesión."},
            status=401,
        )

    selected = request.session.get("selected_exercise")

    if not selected:
        return JsonResponse(
            {"error": "Primero elige una suma desde el banco."},
            status=409,
        )

    exercise = Exercise.objects.filter(
        pk=selected["id"],
        operand_a=selected["operand_a"],
        operand_b=selected["operand_b"],
        is_active=True,
    ).first()

    if (
        exercise is None
        or request.POST.get("exercise_id") != str(exercise.pk)
    ):
        return JsonResponse(
            {
                "error": (
                    "La suma cambió o ya no está disponible. "
                    "Vuelve al banco y elígela nuevamente."
                )
            },
            status=409,
        )

    request.session.pop("confirmed_sum", None)

    form = SumConfirmationForm(request.POST, request.FILES)

    if form.is_valid():
        for name in ("operand_a", "operand_b"):
            if form.cleaned_data[name] != getattr(exercise, name):
                form.add_error(
                    name,
                    "No coincide con la suma elegida. "
                    "Revisa la foto y este número.",
                )

    if form.errors:
        errors = []

        for name, field_errors in form.errors.items():
            label = form.fields[name].label

            for error in field_errors:
                errors.append(f"{label}: {error}")

        return JsonResponse(
            {"error": " ".join(errors)},
            status=400,
        )

    confirmed = {
        "exercise_id": exercise.pk,
        "operand_a": form.cleaned_data["operand_a"],
        "operand_b": form.cleaned_data["operand_b"],
        "written_result": form.cleaned_data["written_result"],
        "source": "manual",
    }

    request.session["confirmed_sum"] = confirmed

    return JsonResponse({
        "ok": True,
        "confirmed": confirmed,
    })