"""Pistas de dos pasos para niños: primero una pregunta, después un ejemplo.

Usan cifras ya confirmadas para orientar una acción; no entregan el resultado.

Cómo están pensadas:

- **Pista 1: una pregunta que orienta.** Lleva al niño a la columna y le hace
  mirar lo importante con sus propios números, sin hacer la cuenta por él.
  Tiene que ser cierta por sí sola: si el niño se queda solo con ella, no debe
  llevarlo a otro error. Por eso, cuando hay una llevada, NO se le pregunta
  «¿cuánto es 2 + 1?» (eso le haría escribir 3), sino «¿te llevaste algo de la
  columna de la derecha?».
- **Pista 2: un ejemplo resuelto con OTROS números.** Le muestra el
  procedimiento completo en una suma parecida y le pide hacer lo mismo con la
  suya. Así aprende el paso, pero el resultado de su suma lo encuentra él.
  Nunca se usan sus números en el ejemplo, ni aparece su resultado.

Frases cortas, en tú, con las letras U, D y C que el niño ve en la tabla.
Siguen pendientes de revisión docente antes del piloto.
"""
from .sum_review import COLUMN_LABELS, COLUMN_NAMES

# Ejemplos resueltos. Se usa el primero que no muestre el resultado del niño.
EJEMPLOS_CONTAR = [(5, 3), (6, 2), (4, 3), (7, 2)]
EJEMPLOS_CERO = [6, 8, 3]
EJEMPLOS_DIEZ_O_MAS = [(7, 6), (8, 5), (9, 4), (6, 6)]
EJEMPLOS_LLEVADA = [(27, 15), (38, 24), (19, 13), (46, 28)]
EJEMPLOS_COLUMNA_VACIA = [(80, 40), (60, 70), (90, 50)]
EJEMPLOS_MARCA = [((6, 7), (3, 4)), ((8, 5), (2, 3)), ((9, 9), (4, 1))]


def _letra(nombre):
    """U, D, C o UM, como en la tabla de la suma."""
    return COLUMN_LABELS[COLUMN_NAMES.index(nombre)]


def _cifras(review, nombre):
    """Las cifras de los dos números en esa columna, sin las casillas vacías."""
    columna = next((c for c in review.get('columns', []) if c['name'] == nombre), None)
    if columna is None:
        return []
    return [c for c in (columna['operand_a'], columna['operand_b']) if c != '']


def _respuesta(review):
    """El resultado correcto, solo para comprobar que ninguna pista lo muestre."""
    columnas = review.get('columns', [])
    a = ''.join(c['operand_a'] for c in columnas) or '0'
    b = ''.join(c['operand_b'] for c in columnas) or '0'
    return str(int(a) + int(b))


def _casilla(review, nombre):
    """Cómo nombrar la casilla del resultado que el niño tiene que revisar."""
    columna = next((c for c in review.get('columns', []) if c['name'] == nombre), None)
    escrito = columna['written_result'] if columna else ''
    return f'donde pusiste el {escrito}' if escrito else 'que dejaste vacía'


def _izquierda_bien(review):
    """¿La columna de la izquierda ya tiene la cifra correcta?

    Pasa cuando el niño sí se llevó el 1 pero se equivocó en la cifra de abajo
    (15 + 25 = 48: el 4 está bien, el 8 no). Entonces hay que decirle que no
    toque esa columna, o sumaría el 1 otra vez y escribiría 50.
    """
    indice = review['column_index'] + 1
    if indice >= len(COLUMN_NAMES):
        return None
    if any(d['index'] == indice for d in review.get('discrepancias') or []):
        # Esa columna también está marcada (por su cifra o por su numerito).
        return None
    nombre = COLUMN_NAMES[indice]
    columna = next((c for c in review.get('columns', []) if c['name'] == nombre), None)
    if columna is None or columna['written_result'] == '':
        return None
    esperado = int(_respuesta(review)) // 10 ** indice % 10
    return COLUMN_LABELS[indice] if columna['written_result'] == str(esperado) else None


def _sin_respuesta(textos, respuesta):
    """El primer texto que no deja ver el resultado del niño."""
    for texto in textos:
        if respuesta not in texto:
            return texto
    return textos[-1]


def _primera(review, nombre, letra, cifras):
    codigo = review['hint_code']
    indice = review['column_index']
    derecha = COLUMN_LABELS[indice - 1] if indice else None
    if codigo == 'carry_annotation':
        return (f'Mira el numerito que anotaste arriba de la columna {letra} ({nombre}). '
                f'Ese numerito sale de la columna de la derecha ({derecha}). '
                '¿Qué te dio esa columna?')
    if codigo == 'extra_column':
        return (f'Mira la columna {letra} ({nombre}), a la izquierda de todo. '
                'Arriba no hay números. ¿De dónde salió el número que escribiste ahí?')
    if codigo == 'incoming_carry':
        return (f'Antes de sumar la columna {letra} ({nombre}), mira la columna de la '
                f'derecha ({derecha}). ¿Te llevaste algo de ahí?')
    if codigo == 'outgoing_carry':
        a, b = cifras
        return (f'En la columna {letra} ({nombre}) tienes {a} y {b}. Súmalos: '
                '¿te da un número de una cifra o de dos cifras?')
    # column_sum: la columna no recibe ni pasa nada, es una suma sencilla.
    if len(cifras) == 2:
        a, b = cifras
        return (f'Vuelve a sumar la columna {letra} ({nombre}): tienes {a} y {b}. '
                'Hazlo con calma y compara con el número que escribiste abajo.')
    return (f'Mira la columna {letra} ({nombre}). Arriba hay un solo número. '
            '¿Te llevaste algo de la columna de la derecha?')


def _segunda(review, letra, cifras):
    codigo = review['hint_code']
    indice = review['column_index']
    derecha = COLUMN_LABELS[indice - 1] if indice else None
    respuesta = _respuesta(review)

    if codigo == 'carry_annotation':
        return _sin_respuesta([
            f'Solo te llevas 1 cuando la columna da 10 o más. Ejemplo: {x} + {y} = {x + y}, '
            f'te llevas 1. Pero {p} + {q} = {p + q}, no te llevas nada. '
            f'¿Qué pasa en tu columna {derecha}?'
            for (x, y), (p, q) in EJEMPLOS_MARCA], respuesta)

    if codigo == 'extra_column':
        return _sin_respuesta([
            f'Un número solo aparece en esa columna si te llevaste algo. Ejemplo: '
            f'{x} + {y} = {x + y}. Ese {str(x + y)[0]} aparece porque {x // 10} + {y // 10} '
            f'da {x // 10 + y // 10}. En tu suma, ¿la columna de al lado dio 10 o más?'
            for x, y in EJEMPLOS_COLUMNA_VACIA], respuesta)

    if codigo == 'incoming_carry':
        if not cifras:
            return _sin_respuesta([
                f'Lo que te llevas baja aunque arriba no haya números. Ejemplo: {x} + {y}. '
                f'En las decenas, {x // 10} + {y // 10} = {x // 10 + y // 10}: abajo va el '
                f'{(x // 10 + y // 10) % 10} y te llevas 1. En las centenas no hay números, '
                f'así que ese 1 baja solo. Resultado: {x + y}. Haz lo mismo en tu columna {letra}.'
                for x, y in EJEMPLOS_COLUMNA_VACIA], respuesta)
        casilla = _casilla(review, review['column_name'])
        return _sin_respuesta([
            f'Lo que te llevas también se suma. Ejemplo: {x} + {y}. En las unidades, '
            f'{x % 10} + {y % 10} = {x % 10 + y % 10}: abajo va el {(x % 10 + y % 10) % 10} '
            f'y te llevas 1. En las decenas: {x // 10} + {y // 10} + el 1 que te llevaste '
            f'= {x // 10 + y // 10 + 1}. Resultado: {x + y}. Ahora suma tu columna {letra} '
            f'contando también lo que te llevaste. ¿Qué cifra va en la casilla {casilla}?'
            for x, y in EJEMPLOS_LLEVADA], respuesta)

    if codigo == 'outgoing_carry':
        propios = {tuple(sorted(int(c) for c in cifras))}
        a, b = cifras
        casilla = _casilla(review, review['column_name'])
        bien = _izquierda_bien(review)
        cierre = (f' Tu columna {bien} ya está bien: ahí sí sumaste lo que te llevaste, '
                  'no la cambies.' if bien else '')
        return _sin_respuesta([
            f'Si una columna da 10 o más, no cabe en una casilla. Ejemplo: {x} + {y} = '
            f'{x + y}. Abajo se escribe el {(x + y) % 10} y el 1 se lleva arriba de la '
            f'columna de la izquierda. Ahora piensa cuánto te dio {a} + {b}. '
            f'¿Qué cifra va en la casilla {casilla}?{cierre}'
            for x, y in EJEMPLOS_DIEZ_O_MAS if tuple(sorted((x, y))) not in propios],
            respuesta)

    # column_sum
    if len(cifras) == 2:
        a, b = int(cifras[0]), int(cifras[1])
        if min(a, b) == 0:
            otro = max(a, b)
            return _sin_respuesta([
                f'Sumar 0 es no agregar nada: el otro número se queda igual. '
                f'Ejemplo: {n} + 0 = {n}. Revisa tu columna {letra} con esa idea.'
                for n in EJEMPLOS_CERO if n != otro], respuesta)
        return _sin_respuesta([
            f'Un truco: empieza en el número más grande y cuenta hacia adelante con tus '
            f'dedos. Ejemplo: {x} + {y} → {x}… '
            f'{", ".join(str(n) for n in range(x + 1, x + y + 1))}. '
            f'Ahora hazlo con los números de tu columna {letra}.'
            for x, y in EJEMPLOS_CONTAR if {x, y} != {a, b}], respuesta)
    return _sin_respuesta([
        'Si en una columna hay un solo número y no te llevaste nada, ese número baja '
        f'igual. Ejemplo: en {x} + {y}, el {x // 10} de las decenas baja tal cual. '
        f'Revisa tu columna {letra} con esa idea.'
        for x, y in ((52, 7), (63, 4), (81, 6))], respuesta)


# La pista 2 se lee en tres partes: la idea, el ejemplo y lo que hace el niño.
# Los saltos de línea las separan en la pantalla (white-space: pre-line).
CORTES = (' Ejemplo:', ' Haz lo mismo', ' Ahora ', ' Revisa tu columna',
          ' ¿Qué pasa en tu columna', ' En tu suma,', ' Tu columna')


def _en_lineas(texto):
    for corte in CORTES:
        texto = texto.replace(corte, '\n' + corte[1:])
    return texto


def hints_for(review):
    """Las dos pistas de la PRIMERA columna por revisar.

    Es el contrato de la API (dos pasos por discrepancia). La pantalla usa
    ``pistas_de``, que recorre todas las columnas.
    """
    if review['status'] != 'requiere_revision':
        return []
    nombre = review['column_name']
    letra = _letra(nombre)
    cifras = _cifras(review, nombre)
    return [_primera(review, nombre, letra, cifras),
            _en_lineas(_segunda(review, letra, cifras))]


# Cuando una columna repite el tipo de error de otra anterior, su pista 2 no
# repite el ejemplo largo: le recuerda la idea con una frase.
RECORDATORIOS = {
    'column_sum': 'Usa el mismo truco que en la columna {antes}: empieza en el número '
                  'más grande y cuenta con tus dedos.',
    'column_sum_cero': 'Igual que en la columna {antes}: sumar 0 no cambia el otro número.',
    'outgoing_carry': 'Igual que en la columna {antes}: si da 10 o más, abajo va solo la '
                      'cifra de la derecha y el 1 se lleva a la izquierda.',
    'incoming_carry': 'Igual que en la columna {antes}: suma también lo que te llevaste '
                      'de la columna de la derecha.',
    'extra_column': 'Igual que en la columna {antes}: ahí solo va un número si te llevaste algo.',
    'carry_annotation': 'Igual que en la columna {antes}: solo te llevas 1 si la columna '
                        'de la derecha dio 10 o más.',
}


def _vista_de_columna(review, discrepancia):
    """La revisión vista desde una sola columna, como si fuera la primera."""
    return {**review, 'column_index': discrepancia['index'],
            'column_name': discrepancia['name'], 'hint_code': discrepancia['hint_code'],
            'mismatch_kind': discrepancia['kind']}


def pistas_de(review):
    """Todas las pistas, columna por columna, de derecha a izquierda.

    Cada columna por revisar trae su pista 1 (pregunta) y su pista 2 (ejemplo).
    Si una columna repite el mismo tipo de error que otra anterior, su pista 2
    no repite el ejemplo largo: le recuerda la idea y le señala la casilla.
    Devuelve diccionarios con ``texto``, ``columna`` (U, D, C, UM) y ``paso``.
    """
    if review['status'] != 'requiere_revision':
        return []
    pistas, vistos = [], {}
    for discrepancia in review.get('discrepancias') or []:
        vista = _vista_de_columna(review, discrepancia)
        nombre, letra, codigo = discrepancia['name'], discrepancia['label'], discrepancia['hint_code']
        cifras = _cifras(vista, nombre)
        primera = _primera(vista, nombre, letra, cifras)
        # Sumar con un 0 es otra idea que contar con los dedos: no se mezclan.
        clave = codigo + ('_cero' if codigo == 'column_sum' and '0' in cifras else '')
        if clave in vistos:
            segunda = (RECORDATORIOS[clave].format(antes=vistos[clave]) + '\n'
                       + (f'¿Qué numerito va arriba de la columna {letra}?'
                          if discrepancia['kind'] == 'carry'
                          else f'¿Qué cifra va en la casilla {_casilla(vista, nombre)}?'))
        else:
            segunda = _en_lineas(_segunda(vista, letra, cifras))
            vistos[clave] = letra
        pistas.append({'texto': primera, 'columna': letra, 'paso': 1})
        pistas.append({'texto': segunda, 'columna': letra, 'paso': 2})
    return pistas
