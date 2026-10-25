import hashlib
import logging
import uuid

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import SESSION_KEY
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from .forms import PhotoUploadForm, SumConfirmationForm
from .models import Exercise
from .services.handwriting import MODELO, ReaderBusy, ReaderUnavailable, leer_fotografia

logger = logging.getLogger(__name__)
READING_SALT = 'tutoring.photo-reading.v1'
READING_MAX_AGE = 30 * 60


def _snapshot(exercise):
    return {'id': exercise.pk, 'operand_a': exercise.operand_a,
            'operand_b': exercise.operand_b}


def _selected_exercise(request):
    selected = request.session.get('selected_exercise')
    if not isinstance(selected, dict):
        return None
    return Exercise.objects.filter(
        pk=selected.get('id'), operand_a=selected.get('operand_a'),
        operand_b=selected.get('operand_b'), is_active=True,
    ).first()


def _photo_context(request):
    if not request.user.is_authenticated:
        return None, JsonResponse(
            {'error': 'Tu sesión terminó. Vuelve a iniciar sesión.'}, status=401,
        )
    if not request.session.get('selected_exercise'):
        return None, JsonResponse(
            {'error': 'Primero elige una suma desde el banco.'}, status=409,
        )
    exercise = _selected_exercise(request)
    if exercise is None or request.POST.get('exercise_id') != str(exercise.pk):
        return None, _exercise_changed()
    return exercise, None


def _exercise_changed():
    return JsonResponse({'error': (
        'La suma cambió o ya no está disponible. Vuelve al banco y elígela nuevamente.'
    )}, status=409)


def _photo_digest(photo):
    digest = hashlib.sha256()
    photo.seek(0)
    for chunk in photo.chunks():
        digest.update(chunk)
    photo.seek(0)
    return digest.hexdigest()


def _receipt_context(request, exercise, photo):
    # El identificador real de sesión nunca sale en el formulario.
    session_hash = hashlib.sha256(request.session.session_key.encode()).hexdigest()
    return {
        'user': str(request.user.pk), 'session': session_hash,
        'exercise': _snapshot(exercise), 'photo': _photo_digest(photo),
    }


@never_cache
@login_required
def exercise_list(request):
    return render(request, 'tutoring/exercise_list.html', {
        'exercises': Exercise.objects.filter(is_active=True),
    })


@never_cache
@login_required(redirect_field_name=None)
@require_POST
def select_exercise(request, pk):
    exercise = Exercise.objects.filter(pk=pk, is_active=True).first()
    if exercise is None:
        messages.info(request, 'Esta suma ya no está disponible. Elige otra.')
        return redirect('tutoring:exercise_list')
    request.session.pop('confirmed_sum', None)
    request.session.pop('sum_review', None)
    request.session.pop('sum_practice', None)
    request.session['selected_exercise'] = _snapshot(exercise)
    return redirect('tutoring:exercise_detail')


@never_cache
@login_required
def exercise_detail(request):
    if not request.session.get('selected_exercise'):
        return redirect('tutoring:exercise_list')
    exercise = _selected_exercise(request)
    if exercise is None:
        request.session.pop('selected_exercise', None)
        request.session.pop('confirmed_sum', None)
        request.session.pop('sum_review', None)
        request.session.pop('sum_practice', None)
        messages.info(request, 'La suma elegida cambió o ya no está disponible. Elige otra.')
        return redirect('tutoring:exercise_list')
    confirmed = request.session.get('confirmed_sum')
    if (not isinstance(confirmed, dict) or confirmed.get('exercise_id') != exercise.pk
            or confirmed.get('operand_a') != exercise.operand_a
            or confirmed.get('operand_b') != exercise.operand_b
            or not confirmed.get('confirmation_id')):
        confirmed = None
    return render(request, 'tutoring/exercise_detail.html', {
        'exercise': exercise, 'confirmation_form': SumConfirmationForm(),
        'confirmed': confirmed,
    })


@never_cache
@require_POST
def upload_photo(request):
    exercise, error = _photo_context(request)
    if error is not None:
        return error

    # Invalidar la confirmación anterior antes de una inferencia larga. Guardarla
    # ahora evita que esta petición sobrescriba después una selección más reciente.
    if 'confirmed_sum' in request.session or 'sum_review' in request.session:
        request.session.pop('confirmed_sum', None)
        request.session.pop('sum_review', None)
        request.session.save()
        request.session.modified = False

    form = PhotoUploadForm(request.POST, request.FILES)
    if not form.is_valid():
        return JsonResponse({'error': form.errors['photo'][0]}, status=400)
    photo = form.cleaned_data['photo']
    try:
        reading = leer_fotografia(photo, getattr(settings, 'HANDWRITING_MODEL', MODELO))
    except ReaderBusy as exc:
        return JsonResponse({'error': str(exc)}, status=429)
    except ReaderUnavailable:
        logger.exception('No se pudo ejecutar el lector; revisa dependencias y caché del modelo.')
        return JsonResponse({'error': (
            'El lector no está disponible en este momento. Vuelve a intentarlo.'
        )}, status=503)

    # La lectura puede tardar: comprobar una selección o cierre de sesión hechos
    # desde otra pestaña sin escribir la sesión que se leyó al iniciar la petición.
    current_session = request.session.load()
    if current_session.get(SESSION_KEY) != str(request.user.pk):
        return JsonResponse({'error': 'Tu sesión terminó. Vuelve a iniciar sesión.'}, status=401)
    if (current_session.get('selected_exercise') != _snapshot(exercise)
            or not Exercise.objects.filter(pk=exercise.pk, is_active=True,
                operand_a=exercise.operand_a, operand_b=exercise.operand_b).exists()):
        return _exercise_changed()

    token = ''
    if reading['can_confirm']:
        receipt = _receipt_context(request, exercise, photo)
        receipt.update(proposal=reading['propuesta'], source=reading['source'])
        token = signing.dumps(receipt, salt=READING_SALT, compress=True)
    return JsonResponse({'ok': True, 'reading': reading, 'reading_token': token})


@never_cache
@require_POST
def confirm_sum(request):
    exercise, error = _photo_context(request)
    if error is not None:
        return error
    request.session.pop('confirmed_sum', None)
    request.session.pop('sum_review', None)
    form = SumConfirmationForm(request.POST, request.FILES)
    if not form.is_valid():
        errors = [f'{form.fields[name].label}: {error}'
                  for name, field_errors in form.errors.items() for error in field_errors]
        return JsonResponse({'error': ' '.join(errors)}, status=400)

    try:
        receipt = signing.loads(request.POST.get('reading_token', ''),
                                salt=READING_SALT, max_age=READING_MAX_AGE)
        expected = _receipt_context(request, exercise, form.cleaned_data['photo'])
        if not isinstance(receipt, dict) or any(receipt.get(k) != v for k, v in expected.items()):
            raise signing.BadSignature('La lectura no corresponde a esta fotografía o sesión.')
    except signing.BadSignature:
        return JsonResponse({'error': (
            'La lectura ya no corresponde a esta fotografía o venció. '
            'Vuelve a cargar la foto y revisa los números.'
        )}, status=409)

    for name in ('operand_a', 'operand_b'):
        if form.cleaned_data[name] != getattr(exercise, name):
            form.add_error(name, 'No coincide con la suma elegida. Revisa la foto y este número.')
    if form.errors:
        errors = [f'{form.fields[name].label}: {error}'
                  for name, field_errors in form.errors.items() for error in field_errors]
        return JsonResponse({'error': ' '.join(errors)}, status=400)

    values = {name: form.cleaned_data[name]
              for name in ('operand_a', 'operand_b', 'written_result')}
    confirmed = {
        'confirmation_id': uuid.uuid4().hex,
        'exercise_id': exercise.pk, **values,
        'source': 'ocr_confirmed' if values == receipt['proposal'] else 'ocr_edited',
        'recognizer': receipt['source'], 'original_proposal': receipt['proposal'],
    }
    request.session['confirmed_sum'] = confirmed
    return JsonResponse({'ok': True, 'confirmed': confirmed})
