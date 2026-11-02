"""Reglas aritméticas sobre números confirmados; no infieren causas del error.

La respuesta correcta y las cifras esperadas no se incluyen en la presentación.
Evalúa únicamente marcas de llevada transcritas y confirmadas por el usuario.
El OCR todavía no reconoce esas marcas.
"""
COLUMN_NAMES = ('unidades', 'decenas', 'centenas', 'unidades de millar')
COLUMN_LABELS = ('U', 'D', 'C', 'UM')


def review_sum(operand_a, operand_b, written_result, *, carries=None):
    for name, value, maximum in (
        ('operand_a', operand_a, 999), ('operand_b', operand_b, 999),
        ('written_result', written_result, 9999),
    ):
        if type(value) is not int or not 0 <= value <= maximum:
            raise ValueError(f'{name} está fuera del alcance de la práctica.')
    if carries is None:
        carries = {}
    if not isinstance(carries, dict) or any(
        key not in COLUMN_NAMES[1:] or type(value) is not int or value not in (0, 1)
        for key, value in carries.items()
    ):
        raise ValueError('Las marcas confirmadas deben ser 0 o 1 en una columna admitida.')
    expected = operand_a + operand_b
    width = max(len(str(n)) for n in (operand_a, operand_b, written_result, expected))
    if carries:
        width = max(width, max(COLUMN_NAMES.index(key) + 1 for key in carries))
    mismatch, hint_code, carry = None, None, 0
    mismatch_kind = None
    columns = []
    for index in range(width):
        place = 10 ** index
        subtotal = operand_a // place % 10 + operand_b // place % 10 + carry
        if mismatch is None and written_result // place % 10 != subtotal % 10:
            mismatch = index
            mismatch_kind = 'result'
            if carry:
                hint_code = 'incoming_carry'
            elif subtotal >= 10:
                hint_code = 'outgoing_carry'
            elif index >= max(len(str(operand_a)), len(str(operand_b))):
                hint_code = 'extra_column'
            else:
                hint_code = 'column_sum'
        written_carry = carries.get(COLUMN_NAMES[index])
        if mismatch is None and written_carry is not None and written_carry != carry:
            mismatch, mismatch_kind, hint_code = index, 'carry', 'carry_annotation'
        carry = subtotal // 10
        columns.append({
            'label': COLUMN_LABELS[index], 'name': COLUMN_NAMES[index],
            'operand_a': str(operand_a)[-1-index] if index < len(str(operand_a)) else '',
            'operand_b': str(operand_b)[-1-index] if index < len(str(operand_b)) else '',
            'written_result': str(written_result)[-1-index] if index < len(str(written_result)) else '',
            'needs_review': mismatch == index,
            'result_needs_review': mismatch == index and mismatch_kind == 'result',
            'carry_needs_review': mismatch == index and mismatch_kind == 'carry',
            'written_carry': str(written_carry) if written_carry is not None else '',
        })
    return {
        'status': 'correcto' if mismatch is None else 'requiere_revision',
        'column_index': mismatch,
        'column_name': COLUMN_NAMES[mismatch] if mismatch is not None else None,
        'hint_code': hint_code, 'columns': list(reversed(columns)),
        'mismatch_kind': mismatch_kind, 'carry_count': len(carries),
    }
