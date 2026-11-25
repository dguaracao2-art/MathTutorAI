"""Pistas de dos pasos, escritas para niños de primeros años de básica.

Usan cifras ya confirmadas para orientar una acción; no entregan el resultado.
Frases cortas, en tú, con las letras U, D y C que el niño ve en la tabla de su
suma. Siguen pendientes de revisión docente antes del piloto.
"""
from .sum_review import COLUMN_LABELS, COLUMN_NAMES

SECOND_HINTS = {
    'carry_annotation': (
        'Suma otra vez la columna de la derecha. Si te da 10 o más, te llevas 1. '
        'Si te da menos de 10, no te llevas nada.'
    ),
    'column_sum': (
        'Suma solo los dos números de esta columna, con calma. '
        '¿Te da lo mismo que escribiste abajo?'
    ),
    'incoming_carry': (
        'Mira la columna de la derecha: ¿te dio 10 o más? '
        'Entonces te llevas 1 a esta columna, y ese 1 también se suma aquí.'
    ),
    'outgoing_carry': (
        'Cuando una columna da 10 o más, abajo escribes solo el número de la '
        'derecha y te llevas 1 a la columna de al lado.'
    ),
    'extra_column': (
        'Ese número solo va si la columna de al lado te dio 10 o más. '
        'Súmala otra vez: ¿te dio 10 o más?'
    ),
}


def _letra(nombre):
    """U, D, C o UM, como en la tabla de la suma."""
    return COLUMN_LABELS[COLUMN_NAMES.index(nombre)]


def hints_for(review):
    if review['status'] != 'requiere_revision':
        return []
    name = review['column_name']
    letra = _letra(name)
    if review.get('mismatch_kind') == 'carry':
        first = (f'Mira la marca pequeña que pusiste arriba de la columna {letra} '
                 f'({name}). Es el número que te llevas. ¿Es igual al de tu hoja?')
    elif review['hint_code'] == 'extra_column':
        # En esa columna no hay números que sumar: solo el que escribió el niño.
        first = (f'Mira la columna {letra} ({name}), a la izquierda de todo. '
                 'Ahí escribiste un número de más.')
    elif name == 'unidades':
        first = ('Empieza por la derecha, en la columna U (unidades). '
                 'Pon tu dedo sobre los dos números de esa columna.')
    else:
        first = (f'Busca la columna {letra} ({name}). '
                 'Pon tu dedo sobre los dos números de esa columna.')
    second = SECOND_HINTS[review['hint_code']]
    if review['hint_code'] == 'column_sum':
        column = next((item for item in review.get('columns', []) if item['name'] == name), None)
        if column is not None:
            a, b = int(column['operand_a'] or 0), int(column['operand_b'] or 0)
            if min(a, b) == 0:
                second = ('Uno de los números es 0. Si sumas 0, el otro número no '
                          'cambia. ¿Qué escribiste tú abajo?')
            else:
                second = (f'Aquí tienes {a} y {b}. Empieza en {max(a, b)} y cuenta '
                          f'{min(a, b)} más con tus dedos. ¿Te da lo mismo que escribiste?')
    return [first, second]
