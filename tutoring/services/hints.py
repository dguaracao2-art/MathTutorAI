"""Pistas de dos pasos, pendientes de revisión docente antes del piloto.

Usan cifras ya confirmadas para orientar una acción; no entregan el resultado.
"""
SECOND_HINTS = {
    'carry_annotation': (
        'Vuelve a la columna anterior y comprueba si formas un grupo de diez. '
        'Solo ese grupo pasa a la siguiente columna. Compara con la marca que anotaste.'
    ),
    'column_sum': (
        'Señala las dos cifras de esta columna. Cuenta sus cantidades juntas '
        'y compara lo que obtienes con la cifra que escribiste.'
    ),
    'incoming_carry': (
        'Antes de sumar esta columna, vuelve a la anterior. Si formas un grupo '
        'de diez, ese grupo pasa a la columna que estás revisando.'
    ),
    'outgoing_carry': (
        'Junta las cantidades de esta columna en grupos de diez. Deja aquí las '
        'unidades sueltas y lleva el grupo de diez a la siguiente columna. '
        'Ahora compara con tu hoja.'
    ),
    'extra_column': (
        'Observa la cifra que añadiste a la izquierda. Revisa si la columna '
        'anterior forma un grupo de diez que deba pasar a ese lugar.'
    ),
}


def hints_for(review):
    if review['status'] != 'requiere_revision':
        return []
    name = review['column_name']
    if review.get('mismatch_kind') == 'carry':
        first = (f'Mira la marca pequeña que confirmaste sobre las {name}. '
                 'Comprueba que es la misma que aparece en tu hoja.')
    elif name == 'unidades':
        first = ('Empieza por la derecha: busca las unidades y señala con tu dedo '
                 'las dos cifras de esa columna. Vamos a trabajar solo ahí.')
    else:
        first = (f'Busca la columna de las {name}. Sigue esa columna con tu dedo '
                 'para localizar las cifras que vas a sumar.')
    second = SECOND_HINTS[review['hint_code']]
    if review['hint_code'] == 'column_sum':
        column = next((item for item in review.get('columns', []) if item['name'] == name), None)
        if column is not None:
            a, b = int(column['operand_a'] or 0), int(column['operand_b'] or 0)
            if min(a, b) == 0:
                second = ('Una de las cifras es 0. Piensa qué ocurre al sumar cero a '
                          'la otra cantidad y compara con lo que escribiste en esa columna.')
            else:
                second = (f'En esta columna tienes {a} y {b}. Empieza por {max(a, b)} '
                          f'y cuenta {min(a, b)} pasos más, uno por cada dedo. '
                          'Compara lo que obtienes con la cifra de tu hoja.')
    return [first, second]
