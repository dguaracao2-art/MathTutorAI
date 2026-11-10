"""Preparar el conjunto de entrenamiento del detector de filas.

Aprovecha la separación con OpenCV ya existente: en las fotografías que el
método actual resuelve bien, sus cajas se convierten en etiquetas. Las que
fallan se informan al final para etiquetarlas a mano; son precisamente las
que más conviene añadir, porque representan los casos que hoy no funcionan.

Las etiquetas se guardan en el espacio de la imagen sin enderezar, que es el
que recibe el detector al leer una foto nueva. No se usa el ejercicio
seleccionado, su resultado ni ningún dato de la base.

    python tools/preparar_dataset_yolo.py local_ocr/pruebas
    python tools/preparar_dataset_yolo.py local_ocr/pruebas --salida local_yolo/dataset
"""
from pathlib import Path
import argparse
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tutoring.services.handwriting import PhotoNotReadable, preparar_suma

EXTENSIONES = {'.jpg', '.jpeg', '.png'}
CLASE = 0
UNA_DE_CADA = 5  # Una imagen de validación por cada cinco.


def imagen_sin_enderezar(ruta):
    """Repetir la apertura de preparar_suma sin la rotación posterior."""
    from PIL import Image, ImageOps

    with Image.open(ruta) as archivo:
        archivo.seek(0)
        imagen = ImageOps.exif_transpose(archivo).convert('RGB')
    imagen.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
    return imagen


def caja_ajustada(mascara, caja):
    """Reducir la caja a la tinta realmente presente dentro de ella."""
    import numpy as np

    x1, y1, x2, y2 = caja
    region = np.asarray(mascara.convert('L'))[y1:y2, x1:x2]
    filas, columnas = np.where(region < 128)
    if not len(filas):
        return caja
    return [x1 + int(columnas.min()), y1 + int(filas.min()),
            x1 + int(columnas.max()) + 1, y1 + int(filas.max()) + 1]


def deshacer_rotacion(caja, angulo, ancho, alto):
    """Llevar una caja del espacio enderezado al de la imagen original."""
    import cv2
    import numpy as np

    if not angulo:
        return caja
    inversa = cv2.getRotationMatrix2D((ancho / 2, alto / 2), -angulo, 1)
    x1, y1, x2, y2 = caja
    esquinas = np.array([[x1, y1, 1], [x2, y1, 1], [x2, y2, 1], [x1, y2, 1]],
                        dtype=float)
    puntos = esquinas @ inversa.T
    return [max(0, int(puntos[:, 0].min())), max(0, int(puntos[:, 1].min())),
            min(ancho, int(puntos[:, 0].max()) + 1),
            min(alto, int(puntos[:, 1].max()) + 1)]


def linea_yolo(caja, ancho, alto):
    """Formato de ultralytics: clase y centro, ancho y alto normalizados."""
    x1, y1, x2, y2 = caja
    return (f'{CLASE} {(x1 + x2) / 2 / ancho:.6f} {(y1 + y2) / 2 / alto:.6f} '
            f'{(x2 - x1) / ancho:.6f} {(y2 - y1) / alto:.6f}')


def etiquetar(ruta):
    """Devolver la imagen sin enderezar y sus tres cajas, o None si falla."""
    try:
        _, mascara, _, cajas, angulo = preparar_suma(ruta, usar_detector=False)
    except (PhotoNotReadable, OSError, ValueError):
        return None
    imagen = imagen_sin_enderezar(ruta)
    ancho, alto = imagen.size
    lineas = []
    for nombre in ('operando_a', 'operando_b', 'resultado'):
        ajustada = caja_ajustada(mascara, cajas[nombre])
        final = deshacer_rotacion(ajustada, angulo, ancho, alto)
        if final[2] - final[0] < 4 or final[3] - final[1] < 4:
            return None
        lineas.append(linea_yolo(final, ancho, alto))
    return imagen, lineas


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('fotografias', type=Path,
                        help='Carpeta con las fotos de sumas ya disponibles.')
    parser.add_argument('--salida', type=Path, default=Path('local_yolo/dataset'))
    args = parser.parse_args()

    rutas = sorted(p for p in args.fotografias.iterdir()
                   if p.suffix.lower() in EXTENSIONES)
    if not rutas:
        parser.exit(1, f'No hay imágenes JPG o PNG en {args.fotografias}.\n')

    for parte in ('train', 'val'):
        (args.salida / 'images' / parte).mkdir(parents=True, exist_ok=True)
        (args.salida / 'labels' / parte).mkdir(parents=True, exist_ok=True)

    etiquetadas, pendientes = [], []
    for indice, ruta in enumerate(rutas):
        resultado = etiquetar(ruta)
        if resultado is None:
            pendientes.append(ruta.name)
            continue
        imagen, lineas = resultado
        parte = 'val' if indice % UNA_DE_CADA == UNA_DE_CADA - 1 else 'train'
        nombre = ruta.stem.replace(' ', '_')
        imagen.save(args.salida / 'images' / parte / f'{nombre}.jpg', quality=92)
        (args.salida / 'labels' / parte / f'{nombre}.txt').write_text(
            '\n'.join(lineas) + '\n', encoding='utf-8')
        etiquetadas.append(f'{nombre}.jpg')

    (args.salida / 'data.yaml').write_text(
        f'path: {args.salida.resolve()}\n'
        'train: images/train\n'
        'val: images/val\n'
        'names:\n'
        '  0: fila\n', encoding='utf-8')

    print(f'Etiquetadas automáticamente: {len(etiquetadas)} de {len(rutas)}')
    print(f'Conjunto preparado en: {args.salida.resolve()}')
    if pendientes:
        print(f'\nSin etiquetar ({len(pendientes)}). Estas son las fotos que el '
              'método actual no separa;\netiquétalas a mano para que el detector '
              'aprenda justamente esos casos:')
        for nombre in pendientes:
            print(f'  - {nombre}')
    if len(etiquetadas) < 20:
        print('\nAviso: con menos de 20 imágenes el entrenamiento no es confiable.')


if __name__ == '__main__':
    main()
