"""Diagnóstico, dos pistas progresivas y reintento dentro de la sesión actual."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from .models import Attempt
from .services.hints import hints_for
from .services.sum_review import review_sum
from .views import _selected_exercise, _snapshot


def _context(request, *, submitted=False, reviewed=False):
    exercise = _selected_exercise(request)
    if exercise is None:
        request.session.pop('confirmed_sum', None)
        request.session.pop('sum_review', None)
        messages.info(request, 'Elige una suma disponible para continuar.')
        return None, None, redirect('tutoring:exercise_list')
    confirmed = request.session.get('confirmed_sum')
    if (not isinstance(confirmed, dict) or not confirmed.get('confirmation_id')
            or confirmed.get('exercise_id') != exercise.pk
            or confirmed.get('operand_a') != exercise.operand_a
            or confirmed.get('operand_b') != exercise.operand_b):
        messages.info(request, 'Primero carga una fotografía y confirma sus números.')
        return None, None, redirect('tutoring:exercise_detail')
    if submitted and (
        request.POST.get('confirmation_id') != confirmed['confirmation_id']
        or request.POST.get('exercise_id') != str(exercise.pk)
    ):
        messages.info(request, 'La lectura cambió. Revisa la fotografía actual antes de continuar.')
        return None, None, redirect('tutoring:exercise_detail')
    state = request.session.get('sum_review', {})
    if reviewed and state.get('confirmation_id') != confirmed['confirmation_id']:
        messages.info(request, 'Pulsa «Comprobar mi suma» después de confirmar la lectura.')
        return None, None, redirect('tutoring:exercise_detail')
    return exercise, confirmed, None


@never_cache
@login_required
@require_POST
def check_sum(request):
    exercise, confirmed, error = _context(request, submitted=True)
    if error is not None:
        return error
    state = request.session.get('sum_review', {})
    # Reenviar el mismo formulario o recargar no añade otro intento.
    if state.get('confirmation_id') != confirmed['confirmation_id']:
        review = review_sum(confirmed['operand_a'], confirmed['operand_b'],
                            confirmed['written_result'], carries=confirmed.get('carries'))
        progress = request.session.get('sum_practice', {})
        if progress.get('exercise') != _snapshot(exercise):
            progress = {'exercise': _snapshot(exercise), 'attempts': 0, 'had_error': False}
        progress = {**progress, 'attempts': progress['attempts'] + 1}
        corrected = review['status'] == 'correcto' and progress['had_error']
        # La restricción única evita duplicados por doble clic o reenvío.
        Attempt.objects.get_or_create(
            confirmation_id=confirmed['confirmation_id'],
            defaults={
                'user': request.user, 'exercise': exercise,
                'operand_a': confirmed['operand_a'], 'operand_b': confirmed['operand_b'],
                'written_result': confirmed['written_result'],
                'carries': confirmed.get('carries', {}),
                'status': 'corregido' if corrected else review['status'],
            },
        )
        if review['status'] == 'requiere_revision':
            progress['had_error'] = True
        request.session['sum_practice'] = progress
        request.session['sum_review'] = {
            'confirmation_id': confirmed['confirmation_id'],
            'hint_level': 0, 'corrected': corrected,
        }
    return redirect('tutoring:review_result')


@never_cache
@login_required
def review_result(request):
    exercise, confirmed, error = _context(request, reviewed=True)
    if error is not None:
        return error
    review = review_sum(confirmed['operand_a'], confirmed['operand_b'],
                            confirmed['written_result'], carries=confirmed.get('carries'))
    state = request.session['sum_review']
    available = hints_for(review)
    level = state['hint_level']
    return render(request, 'tutoring/sum_result.html', {
        'exercise': exercise, 'confirmed': confirmed, 'review': review,
        'hints': available[:level], 'next_hint': level + 1 if level < len(available) else None,
        'hint_count': level, 'corrected': state['corrected'],
        'attempt_count': request.session['sum_practice']['attempts'],
    })


@never_cache
@login_required
@require_POST
def show_hint(request):
    _, confirmed, error = _context(request, submitted=True, reviewed=True)
    if error is not None:
        return error
    review = review_sum(confirmed['operand_a'], confirmed['operand_b'],
                            confirmed['written_result'], carries=confirmed.get('carries'))
    state = request.session['sum_review']
    level = state['hint_level']
    if review['status'] == 'requiere_revision' and level < 2:
        if request.POST.get('level') == str(level + 1):
            request.session['sum_review'] = {**state, 'hint_level': level + 1}
            Attempt.objects.filter(
                user=request.user, confirmation_id=confirmed['confirmation_id'],
                hint_count__lt=level + 1,
            ).update(hint_count=level + 1)
        elif request.POST.get('level') != str(level):
            messages.info(request, 'Consulta primero la siguiente pista disponible.')
    return redirect('tutoring:review_result')


@never_cache
@login_required
@require_POST
def retry_sum(request):
    _, _, error = _context(request, submitted=True, reviewed=True)
    if error is not None:
        return error
    request.session.pop('confirmed_sum', None)
    request.session.pop('sum_review', None)
    messages.info(request, 'Corrige la suma en tu hoja. Después carga o captura una nueva fotografía.')
    return redirect('tutoring:exercise_detail')


@never_cache
@login_required
def progress(request):
    attempts = Attempt.objects.filter(user=request.user).select_related('exercise')
    seen = {}
    for attempt in attempts:
        key = attempt.exercise_id
        if key not in seen:
            seen[key] = {
                'exercise': f'{attempt.operand_a} + {attempt.operand_b}',
                'date': attempt.created_at, 'status': attempt.get_status_display(),
                'attempts': 0, 'hints': 0,
            }
        seen[key]['attempts'] += 1
        seen[key]['hints'] += attempt.hint_count
    return render(request, 'tutoring/progress.html', {'records': list(seen.values())})
