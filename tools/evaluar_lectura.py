"""Evaluar una carpeta local de fotos, sin copiarlas ni subirlas a ningún sitio."""
import argparse
import csv
from pathlib import Path
import sys
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tutoring.services.handwriting import (  # noqa: E402
    CAMPOS, MODELO, ReaderUnavailable, cargar_modelo, leer_fotografia,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('carpeta', type=Path, help='Ejemplo: local_ocr/pruebas')
    args = parser.parse_args()
    if not args.carpeta.is_dir():
        parser.error('La carpeta indicada no existe.')
    fotos = sorted(p for p in args.carpeta.iterdir()
                   if p.is_file() and p.suffix.lower() in ('.jpg', '.jpeg', '.png'))
    if not fotos:
        parser.error('No hay fotografías JPG o PNG en esa carpeta.')

    inicio = perf_counter()
    print('Cargando el modelo local una sola vez...', flush=True)
    try:
        cargar_modelo(MODELO, True)
    except (ImportError, OSError, RuntimeError, ValueError) as exc:
        print(f'No se pudo cargar el lector local: {exc}', file=sys.stderr)
        return 1
    print(f'Modelo listo en {perf_counter() - inicio:.2f} s.', flush=True)

    filas = []
    for foto in fotos:
        inicio = perf_counter()
        try:
            lectura = leer_fotografia(foto)
        except (ReaderUnavailable, OSError) as exc:
            print(f'No se pudo completar la evaluación: {exc}', file=sys.stderr)
            return 1
        valores = lectura['propuesta']
        segundos = round(perf_counter() - inicio, 3)
        filas.append({'archivo': foto.name, 'estado': lectura['estado'],
                      **valores, 'segundos': segundos})
        numeros = ' / '.join('?' if valores[c] is None else str(valores[c]) for c in CAMPOS)
        print(f'{foto.name}: {numeros} | {lectura["estado"]} | {segundos:.2f} s', flush=True)

    salida = args.carpeta / 'evaluacion_lectura.csv'
    with salida.open('w', newline='', encoding='utf-8-sig') as archivo:
        writer = csv.DictWriter(archivo, fieldnames=('archivo', 'estado', *CAMPOS, 'segundos'))
        writer.writeheader()
        writer.writerows(filas)
    print(f'Resumen guardado en: {salida}')
    print('Compara las propuestas con las fotos: lectura completa no significa lectura correcta.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
