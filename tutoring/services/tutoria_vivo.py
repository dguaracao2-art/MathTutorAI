"""Tutoría en tiempo real: pistas sin recargar y progreso que se actualiza solo.

Lo usan el canal ``/ws/tutoria/`` y las vistas HTTP de la revisión. Aquí no
hay reglas nuevas: las pistas salen de ``pistas_de`` y la revisión de
``review_sum``, igual que en la pantalla de siempre. El canal solo cambia
cómo llegan al estudiante.

Dos cosas que este módulo cuida a propósito:

- La revisión se hace después de «Comprobar mi suma», nunca mientras el
  estudiante edita los números. Si la suma se revisara en vivo al escribir,
  podría ir cambiando el resultado hasta ver «correcto» sin corregir su hoja.
- La sesión se vuelve a leer en cada pista. El canal puede quedar abierto
  mucho rato, y mientras tanto el estudiante pudo empezar otra suma en otra
  pestaña; guardar una copia vieja de la sesión borraría ese avance.

El aviso de progreso viaja por la capa de canales en memoria, que basta con
un solo proceso de daphne. Cada usuario tiene su propio grupo: nadie recibe
el progreso de otro.
"""
from __future__ import annotations

import logging
from importlib import import_module

from django.conf import settings
from django.utils import timezone
from django.utils.dateformat import format as formatear_fecha

from ..models import Attempt
from .hints import pistas_de
from .sum_review import review_sum

logger = logging.getLogger(__name__)

AVISO_LECTURA = 'La foto cambió. Revisa los números de la foto nueva antes de seguir.'
AVISO_SIN_PISTAS = 'Ya no hay más pistas para esta suma.'
AVISO_ORDEN = 'Pide primero la pista que sigue.'

# Cómo se ve el estado de cada suma en «Mi progreso». Se traduce aquí y no en
# el modelo: cambiar las opciones del modelo pediría una migración.
ESTADOS_PARA_NINOS = {
    'correcto': '¡Correcta!',
    'corregido': '¡La corregiste!',
    'requiere_revision': 'Por corregir',
}


def grupo_de(user_id):
    """Nombre del grupo de canales que recibe el progreso de un usuario."""
    return f'tutoria_{int(user_id)}'


def registros_de(user):
    """Resumen por suma de los intentos del usuario, el más reciente primero.

    Es el mismo cálculo que mostraba la página «Mi progreso»; vive aquí para
    que la página y el canal no puedan contar distinto.
    """
    intentos = Attempt.objects.filter(user=user).select_related('exercise')
    vistos = {}
    for intento in intentos:
        clave = intento.exercise_id
        if clave not in vistos:
            vistos[clave] = {
                'exercise': f'{intento.operand_a} + {intento.operand_b}',
                'date': intento.created_at,
                'status': ESTADOS_PARA_NINOS.get(intento.status, intento.get_status_display()),
                'attempts': 0, 'hints': 0,
            }
        vistos[clave]['attempts'] += 1
        vistos[clave]['hints'] += intento.hint_count
    return list(vistos.values())


def registros_para_enviar(user):
    """Los mismos registros, con la fecha ya escrita como en la página."""
    salida = []
    for registro in registros_de(user):
        fecha = timezone.localtime(registro['date'])
        salida.append({**registro, 'date': formatear_fecha(fecha, 'd/m/Y H:i')})
    return salida


def _sesion(clave):
    almacen = import_module(settings.SESSION_ENGINE).SessionStore
    return almacen(session_key=clave)


def pedir_pista(clave_sesion, user, confirmation_id, nivel):
    """Entregar la pista ``nivel`` con las mismas reglas que la vista HTTP.

    Devuelve un diccionario listo para enviar: ``{"tipo": "pista", ...}`` o
    ``{"tipo": "aviso", "texto": ...}``. Ante un aviso el navegador envía el
    formulario de siempre, y la vista HTTP muestra el mensaje y la pantalla
    que correspondan.
    """
    sesion = _sesion(clave_sesion)
    confirmada = sesion.get('confirmed_sum')
    estado = sesion.get('sum_review', {})
    if (not isinstance(confirmada, dict) or not isinstance(estado, dict)
            or not confirmation_id
            or confirmada.get('confirmation_id') != confirmation_id
            or estado.get('confirmation_id') != confirmation_id):
        return {'tipo': 'aviso', 'texto': AVISO_LECTURA}

    revision = review_sum(confirmada['operand_a'], confirmada['operand_b'],
                          confirmada['written_result'], carries=confirmada.get('carries'))
    disponibles = pistas_de(revision)
    actual = estado.get('hint_level', 0)
    if revision['status'] != 'requiere_revision' or not disponibles:
        return {'tipo': 'aviso', 'texto': AVISO_SIN_PISTAS}

    if nivel == actual and actual >= 1:
        # Doble clic o mensaje repetido: se repite la pista sin contarla dos veces.
        pass
    elif nivel == actual + 1 and nivel <= len(disponibles):
        sesion['sum_review'] = {**estado, 'hint_level': nivel}
        sesion.save()
        Attempt.objects.filter(
            user=user, confirmation_id=confirmation_id, hint_count__lt=nivel,
        ).update(hint_count=nivel)
    else:
        return {'tipo': 'aviso', 'texto': AVISO_ORDEN}

    pista = disponibles[nivel - 1]
    siguiente = disponibles[nivel] if nivel < len(disponibles) else None
    return {
        'tipo': 'pista', 'nivel': nivel, 'texto': pista['texto'],
        'titulo': f"Pista {pista['paso']} · columna {pista['columna']}",
        'siguiente': nivel + 1 if siguiente else None,
        'boton': (f"Ver pista {siguiente['paso']} de la columna {siguiente['columna']}"
                  if siguiente else None),
    }


def avisar_progreso(user_id):
    """Pedir a las pantallas abiertas del usuario que actualicen su progreso.

    Nunca interrumpe a quien la llama: si la capa de canales falla, la
    revisión ya quedó guardada y la página de progreso la mostrará al recargar.
    """
    try:
        from asgiref.sync import async_to_sync
        from channels.layers import get_channel_layer

        capa = get_channel_layer()
        if capa is None:
            return
        async_to_sync(capa.group_send)(grupo_de(user_id), {'type': 'progreso.actualizado'})
    except Exception:
        logger.exception('No se pudo avisar del progreso en tiempo real')
