"""Averiguar por qué el borrado de la raya solo movió la exactitud dos puntos.

Compara las 50 fotografías con y sin el arreglo, pero campo por campo en lugar
de solo "la lectura entera coincide". Sin ese desglose no se puede saber si el
problema es que la raya no se está borrando o que, borrada, la lectura falla
igual por otro motivo.

Para cada fotografía informa de tres cosas:

- Si el borrado llegó a dispararse sobre el recorte del segundo sumando.
- Qué campos acierta sin el arreglo y cuáles con él.
- En qué fotografías el arreglo cambió algo, para bien o para mal.

Uso:
    python tools/diagnosticar_raya.py local_ocr/evaluacion_ocr
"""
import argparse
import csv
import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

CAMPOS = ('operand_a', 'operand_b', 'written_result')
FORMATOS = {'.jpg', '.jpeg', '.png'}


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


def normalizar(valor):
    return ''.join(ch for ch in str(valor or '') if ch.isdigit())


def main():
    analizador = argparse.ArgumentParser(description=__doc__)
    analizador.add_argument('carpeta', type=Path)
    argumentos = analizador.parse_args()

    from tutoring.services import handwriting as hw

    esperado = referencia_de(argumentos.carpeta)
    fotos = sorted(p for p in argumentos.carpeta.iterdir()
                   if p.suffix.lower() in FORMATOS and p.name in esperado)
    if not fotos:
        raise SystemExit('No hay fotografías con referencia en esa carpeta.')

    print('Cargando el modelo...', flush=True)
    hw.cargar_modelo(hw.MODELO, True)

    # Contar cuántas veces se dispara el borrado, envolviendo la función real.
    original = hw._quitar_raya_horizontal
    disparos = {'n': 0}

    def espia(recorte):
        salida = original(recorte)
        if salida is not recorte:
            disparos['n'] += 1
        return salida

    hw._quitar_raya_horizontal = espia

    aciertos = {'sin': dict.fromkeys(CAMPOS, 0), 'con': dict.fromkeys(CAMPOS, 0)}
    enteras = {'sin': 0, 'con': 0}
    borrada_en = []
    cambios = []

    for indice, foto in enumerate(fotos, 1):
        referencia = esperado[foto.name]
        lecturas = {}
        for etiqueta, activo in (('sin', '0'), ('con', '1')):
            os.environ['QUITAR_RAYA'] = activo
            antes = disparos['n']
            try:
                salida = hw.leer_fotografia(foto)
            except Exception as exc:  # noqa: BLE001
                print(f'  {foto.name}: fallo ({exc})')
                salida = {'propuesta': dict.fromkeys(CAMPOS)}
            propuesta = salida.get('propuesta') or {}
            lecturas[etiqueta] = {c: normalizar(propuesta.get(c)) for c in CAMPOS}
            if etiqueta == 'con' and disparos['n'] > antes:
                borrada_en.append(foto.name)

        for etiqueta in ('sin', 'con'):
            bien = 0
            for campo in CAMPOS:
                if lecturas[etiqueta][campo] == normalizar(referencia[campo]):
                    aciertos[etiqueta][campo] += 1
                    bien += 1
            if bien == len(CAMPOS):
                enteras[etiqueta] += 1

        if lecturas['sin'] != lecturas['con']:
            cambios.append((foto.name, referencia, lecturas['sin'], lecturas['con']))

        print(f'  {indice}/{len(fotos)} {foto.name}', flush=True)

    hw._quitar_raya_horizontal = original
    os.environ.pop('QUITAR_RAYA', None)

    total = len(fotos)
    print()
    print('=' * 64)
    print(f'Fotografías: {total}')
    print(f'El borrado se disparó en {len(borrada_en)} de {total} recortes '
          f'del segundo sumando.')
    print()
    print(f'{"campo":16s} {"sin arreglo":>12s} {"con arreglo":>12s}')
    for campo in CAMPOS:
        print(f'{campo:16s} {aciertos["sin"][campo]:>9d}/{total} '
              f'{aciertos["con"][campo]:>9d}/{total}')
    print(f'{"lectura entera":16s} {enteras["sin"]:>9d}/{total} '
          f'{enteras["con"]:>9d}/{total}')

    print()
    print(f'Fotografías donde el arreglo cambió la lectura: {len(cambios)}')
    for nombre, referencia, sin, con in cambios:
        print(f'  {nombre}')
        for campo in CAMPOS:
            if sin[campo] != con[campo]:
                correcto = normalizar(referencia[campo])
                marca_sin = '+' if sin[campo] == correcto else '-'
                marca_con = '+' if con[campo] == correcto else '-'
                print(f'      {campo:14s} esperado {correcto!r:>8s}   '
                      f'sin {marca_sin} {sin[campo]!r:>8s}   '
                      f'con {marca_con} {con[campo]!r:>8s}')

    if not borrada_en:
        print()
        print('AVISO: el borrado no se disparó ni una vez. El problema no es')
        print('que la raya resista, es que no se está detectando.')


if __name__ == '__main__':
    raise SystemExit(main())