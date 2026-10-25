"""Reglas aritméticas sobre números confirmados; no infieren causas del error.

La respuesta correcta y las cifras esperadas no se incluyen en la presentación.
No reconoce ni evalúa llevadas manuscritas: el OCR aún no las transcribe.
"""
COLUMN_NAMES = ('unidades', 'decenas', 'centenas', 'unidades de millar')
COLUMN_LABELS = ('U', 'D', 'C', 'UM')


def review_sum(operand_a, operand_b, written_result):
    for name, value, maximum in (
        ('operand_a', operand_a, 999), ('operand_b', operand_b, 999),
        ('written_result', written_result, 9999),
    ):
        if type(value) is not int or not 0 <= value <= maximum:
            raise ValueError(f'{name} está fuera del alcance de la práctica.')
    expected = operand_a + operand_b
    width = max(len(str(n)) for n in (operand_a, operand_b, written_result, expected))
    mismatch, hint_code, carry = None, None, 0
    columns = []
    for index in range(width):
        place = 10 ** index
        subtotal = operand_a // place % 10 + operand_b // place % 10 + carry
        if mismatch is None and written_result // place % 10 != subtotal % 10:
            mismatch = index
            if carry:
                hint_code = 'incoming_carry'
            elif subtotal >= 10:
                hint_code = 'outgoing_carry'
            elif index >= max(len(str(operand_a)), len(str(operand_b))):
                hint_code = 'extra_column'
            else:
                hint_code = 'column_sum'
        carry = subtotal // 10
        columns.append({
            'label': COLUMN_LABELS[index], 'name': COLUMN_NAMES[index],
            'operand_a': str(operand_a)[-1-index] if index < len(str(operand_a)) else '',
            'operand_b': str(operand_b)[-1-index] if index < len(str(operand_b)) else '',
            'written_result': str(written_result)[-1-index] if index < len(str(written_result)) else '',
            'needs_review': mismatch == index,
        })
    return {
        'status': 'correcto' if mismatch is None else 'requiere_revision',
        'column_index': mismatch,
        'column_name': COLUMN_NAMES[mismatch] if mismatch is not None else None,
        'hint_code': hint_code, 'columns': list(reversed(columns)),
    }
