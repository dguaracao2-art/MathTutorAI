"""Clasificar cómo falla la lectura, campo por campo y error por error.

Saber que operand_b acierta 29 de 50 no dice qué hay que arreglar. No es lo
mismo que el lector añada un dígito de más al principio (probablemente el
signo +), que lo añada al final (probablemente la raya de la suma), o que
confunda las cifras en sí (eso sería el modelo, y no hay recorte que lo
arregle).

Este guion separa esos casos. Para cada campo clasifica el error en:

- exacto .............. coincide con la referencia
- sobra_izquierda ..... la referencia está al final de lo leído
- sobra_derecha ....... la referencia está al principio de lo leído
- sobra_en_medio ...... la referencia está dentro, con ruido a ambos lados
- falta_un_digito ..... lo leído está contenido en la referencia
- vacio ............... no devolvió nada
- cifras_erroneas ..... misma longitud, dígitos distintos
- otro ................ ninguno de los anteriores

Uso:
    python tools/diagnosticar_lectura.py local_ocr/evaluacion_ocr
"""
import argparse
import csv
import sys
from collections import Counter, defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

CAMPOS = ('operand_a', 'operand_b', 'written_result')
FORMATOS = {'.jpg', '.jpeg', '.png'}
_TIPOS = ('exacto', 'sobra_izquierda', 'sobra_derecha', 'sobra_en_medio',
          'falta_un_digito', 'vacio', 'cifras_erroneas', 'otro')
# Los "descartado_*" son lecturas que el filtro de longitud tiró enteras. Se
# clasifican por lo que el lector sí había visto, que es lo que dice si había
# forma de recuperarlas.
ORDEN = _TIPOS + tuple('descartado_' + t for t in _TIPOS if t != 'vacio')


def referencia_de(carpeta):
    ruta = carpeta / 'referencia_ocr.csv'
    if not ruta.is_file():
        raise SystemExit(f'No se encuentra {ruta}')
    with ruta.open(encoding='utf-8-sig', newline='') as archivo:
        primera = archivo.readline()
        archivo.seek(0)
        lector = csv.DictReader(archivo, delimiter=';' if ';' in primera else ',')
        return {
            fila['archivo'].strip(): {
                campo: (fila.get(campo) or '').strip() for campo in CAMPOS
            }
            for fila in lector if (fila.get('archivo') or '').strip()
        }


def solo_digitos(valor):
    return ''.join(ch for ch in str(valor if valor is not None else '') if ch.isdigit())


def clasificar(leido, esperado):
    if not esperado:
        return 'otro'
    if leido == esperado:
        return 'exacto'
    if not leido:
        return 'vacio'
    if esperado in leido:
        if leido.endswith(esperado):
            return 'sobra_izquierda'
        if leido.startswith(esperado):
            return 'sobra_derecha'
        return 'sobra_en_medio'
    if leido in esperado:
        return 'falta_un_digito'
    if len(leido) == len(esperado):
        return 'cifras_erroneas'
    return 'otro'


def main():
    analizador = argparse.ArgumentParser(description=__doc__)
    analizador.add_argument('carpeta', type=Path)
    analizador.add_argument('--ejemplos', type=int, default=4,
                            help='Cuántos ejemplos mostrar por tipo de error.')
    argumentos = analizador.parse_args()

    from tutoring.services import handwriting as hw

    esperado = referencia_de(argumentos.carpeta)
    fotos = sorted(p for p in argumentos.carpeta.iterdir()
                   if p.suffix.lower() in FORMATOS and p.name in esperado)
    if not fotos:
        raise SystemExit('No hay fotografías con referencia en esa carpeta.')

    print(f'Modelo: {hw.MODELO}')
    print('Cargando...', flush=True)
    hw.cargar_modelo(hw.MODELO, True)

    cuentas = {campo: Counter() for campo in CAMPOS}
    ejemplos = {campo: defaultdict(list) for campo in CAMPOS}
    fallos_de_separacion = 0

    for indice, foto in enumerate(fotos, 1):
        referencia = esperado[foto.name]
        try:
            salida = hw.leer_fotografia(foto, incluir_diagnostico=True)
        except Exception as exc:  # noqa: BLE001
            print(f'  {foto.name}: fallo ({exc})')
            continue
        if salida.get('etapa') == 'separacion':
            fallos_de_separacion += 1
            print(f'  {indice}/{len(fotos)} {foto.name}  (separación fallida)',
                  flush=True)
            continue

        propuesta = salida.get('propuesta') or {}
        crudas = salida.get('lecturas_crudas') or {}
        for campo in CAMPOS:
            leido = solo_digitos(propuesta.get(campo))
            correcto = solo_digitos(referencia[campo])
            # El texto tal como salió del lector, antes del filtro que
            # descarta lo que no cabe en tres o cuatro dígitos. Es donde se
            # ve qué sobra y de qué lado.
            crudo = solo_digitos(crudas.get(campo, ''))
            tipo = clasificar(leido, correcto)
            cuentas[campo][tipo] += 1
            if tipo == 'vacio' and crudo:
                # Reclasificar el descarte según lo que el lector sí vio.
                cuentas[campo]['vacio'] -= 1
                cuentas[campo]['descartado_' + clasificar(crudo, correcto)] += 1
            if tipo != 'exacto':
                ejemplos[campo][tipo].append((foto.name, correcto, leido, crudo))
        print(f'  {indice}/{len(fotos)} {foto.name}', flush=True)

    total = sum(cuentas['operand_a'].values())
    print()
    print('=' * 70)
    print(f'Fotografías leídas: {total}'
          + (f'  (y {fallos_de_separacion} sin separar)'
             if fallos_de_separacion else ''))
    print()

    encabezado = f'{"tipo de error":18s}' + ''.join(f'{c:>16s}' for c in CAMPOS)
    print(encabezado)
    print('-' * len(encabezado))
    for tipo in ORDEN:
        if not any(cuentas[c][tipo] for c in CAMPOS):
            continue
        fila = f'{tipo:18s}' + ''.join(f'{cuentas[c][tipo]:>16d}' for c in CAMPOS)
        print(fila)

    print()
    print('Ejemplos por campo y tipo de error')
    print('(referencia -> leído)')
    for campo in CAMPOS:
        pendientes = {t: v for t, v in ejemplos[campo].items() if v}
        if not pendientes:
            continue
        print(f'\n  {campo}')
        for tipo in ORDEN:
            casos = pendientes.get(tipo)
            if not casos:
                continue
            print(f'    {tipo}:')
            for nombre, correcto, leido, crudo in casos[:argumentos.ejemplos]:
                extra = f'   (el lector vio {crudo!r})' if crudo and crudo != leido else ''
                print(f'      {nombre:14s} {correcto!r:>8s} -> {leido!r}{extra}')
            if len(casos) > argumentos.ejemplos:
                print(f'      ... y {len(casos) - argumentos.ejemplos} más')

    print()
    print('Cómo leer esto:')
    print('  Mucho "sobra_izquierda" apunta al signo + dentro del recorte.')
    print('  Mucho "sobra_derecha", a la raya de la suma.')
    print('  Mucho "cifras_erroneas", al modelo: el recorte ya no es el problema.')
    print('  Los "descartado_*" son lecturas que el filtro de longitud tiró')
    print('  enteras. Si predomina descartado_sobra_izquierda o _derecha, la')
    print('  cifra correcta estaba ahí y bastaría recortar el sobrante en vez')
    print('  de devolver un campo vacio.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())