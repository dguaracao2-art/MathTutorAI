"""Catálogo inicial pendiente de revisión docente antes del piloto.

No revela respuestas ni atribuye causas no observadas. No genera texto con IA.
"""
SECOND_HINTS = {
    'column_sum': (
        'Suma las cifras de esta columna y compara con lo que escribiste. '
        'Comprueba que las unidades estén con las unidades y las decenas con las decenas.'
    ),
    'incoming_carry': (
        'Al sumar la columna anterior, comprueba si se forma una decena que debes '
        'añadir a esta columna. Después revisa la cifra que escribiste aquí.'
    ),
    'outgoing_carry': (
        'Suma las cifras de esta columna. Si juntas diez o más, escribe aquí solo '
        'las unidades y lleva una a la columna siguiente.'
    ),
    'extra_column': (
        'Comprueba cuántas columnas necesitas para esta suma. Revisa si hay '
        'una llevada que justifique la cifra que escribiste en esta columna.'
    ),
}


def hints_for(review):
    if review['status'] != 'requiere_revision':
        return []
    return [
        f"Revisa la columna de las {review['column_name']}. Vuelve a calcularla en tu hoja.",
        SECOND_HINTS[review['hint_code']],
    ]
