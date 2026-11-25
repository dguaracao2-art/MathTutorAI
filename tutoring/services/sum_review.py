"""Reglas aritméticas sobre números confirmados; no infieren causas del error.

Además de la primera discrepancia (el contrato de RNF-06, que siguen usando la
API y las pruebas de aceptación), se devuelven TODAS las columnas por revisar
en ``discrepancias``. Así el niño ve de una vez todo lo que debe corregir y no
tiene que reescribir su suma con esfero una vez por cada columna.

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
    discrepancias = []
    for index in range(width):
        place = 10 ** index
        subtotal = operand_a // place % 10 + operand_b // place % 10 + carry
        written_carry = carries.get(COLUMN_NAMES[index])
        # Cada columna se juzga con la llevada correcta, no con la del niño.
        kind_here, code_here = None, None
        if written_result // place % 10 != subtotal % 10:
            kind_here = 'result'
            if carry:
                code_here = 'incoming_carry'
            elif subtotal >= 10:
                code_here = 'outgoing_carry'
            elif index >= max(len(str(operand_a)), len(str(operand_b))):
                code_here = 'extra_column'
            else:
                code_here = 'column_sum'
        elif written_carry is not None and written_carry != carry:
            kind_here, code_here = 'carry', 'carry_annotation'
        if kind_here is not None:
            discrepancias.append({
                'index': index, 'name': COLUMN_NAMES[index], 'label': COLUMN_LABELS[index],
                'kind': kind_here, 'hint_code': code_here,
            })
            if mismatch is None:
                mismatch, mismatch_kind, hint_code = index, kind_here, code_here
        carry = subtotal // 10
        columns.append({
            'label': COLUMN_LABELS[index], 'name': COLUMN_NAMES[index],
            'operand_a': str(operand_a)[-1-index] if index < len(str(operand_a)) else '',
            'operand_b': str(operand_b)[-1-index] if index < len(str(operand_b)) else '',
            'written_result': str(written_result)[-1-index] if index < len(str(written_result)) else '',
            'needs_review': mismatch == index,
            'result_needs_review': mismatch == index and mismatch_kind == 'result',
            'carry_needs_review': mismatch == index and mismatch_kind == 'carry',
            'por_revisar': kind_here is not None,
            'resultado_por_revisar': kind_here == 'result',
            'llevada_por_revisar': kind_here == 'carry',
            'written_carry': str(written_carry) if written_carry is not None else '',
        })
    return {
        'status': 'correcto' if mismatch is None else 'requiere_revision',
        'column_index': mismatch,
        'column_name': COLUMN_NAMES[mismatch] if mismatch is not None else None,
        'hint_code': hint_code, 'columns': list(reversed(columns)),
        'mismatch_kind': mismatch_kind, 'carry_count': len(carries),
        'discrepancias': discrepancias,
    }
