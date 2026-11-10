"""Comparar la separación de filas con OpenCV y con el detector YOLO.

Mide una sola etapa: si cada método logra aislar dos operandos y un
resultado. No mide el reconocimiento de las cifras, que sigue a cargo de
TrOCR y se evalúa con tools/medir_exactitud.py. Separar bien es condición
previa para leer, no garantía de leer bien.

Usa fotografías que no se hayan empleado para entrenar el detector; en caso
contrario el resultado del detector será optimista y no debe presentarse
como evidencia.

    python tools/comparar_separacion.py local_ocr/evaluacion_ocr
    python tools/comparar_separacion.py local_ocr/pruebas --salida local_yolo/comparacion
"""
from pathlib import Path
import argparse
import csv
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tutoring.services.handwriting import PhotoNotReadable, preparar_suma
from tutoring.services.yolo_segmentation import (
    RUTA_MODELO, modelo_disponible, separar_con_yolo,
)

EXTENSIONES = {'.jpg', '.jpeg', '.png'}


def imagen_preparada(ruta):
    """Abrir la foto igual que preparar_suma, sin enderezarla."""
    from PIL import Image, ImageOps

    with Image.open(ruta) as archivo:
        archivo.seek(0)
        imagen = ImageOps.exif_transpose(archivo).convert('RGB')
    imagen.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
    return imagen


def separa_con_opencv(ruta):
    try:
        preparar_suma(ruta, usar_detector=False)
    except (PhotoNotReadable, OSError, ValueError) as exc:
        return False, str(exc)
    return True, ''


def separa_con_detector(ruta):
    try:
        imagen = imagen_preparada(ruta)
    except (OSError, ValueError) as exc:
        return False, str(exc)
    if separar_con_yolo(imagen) is None:
        return False, 'El detector no encontró tres filas utilizables.'
    return True, ''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('fotografias', type=Path)
    parser.add_argument('--salida', type=Path, default=Path('local_yolo/comparacion'))
    args = parser.parse_args()

    rutas = sorted(p for p in args.fotografias.iterdir()
                   if p.suffix.lower() in EXTENSIONES)
    if not rutas:
        parser.exit(1, f'No hay imágenes JPG o PNG en {args.fotografias}.\n')
    hay_detector = modelo_disponible()
    if not hay_detector:
        print(f'Aviso: no hay detector en {RUTA_MODELO}. Se informa solo OpenCV.\n')

    filas = []
    for ruta in rutas:
        opencv_ok, motivo_opencv = separa_con_opencv(ruta)
        if hay_detector:
            yolo_ok, motivo_yolo = separa_con_detector(ruta)
        else:
            yolo_ok, motivo_yolo = None, 'sin modelo'
        filas.append({
            'archivo': ruta.name,
            'opencv': 'si' if opencv_ok else 'no',
            'yolo': '' if yolo_ok is None else ('si' if yolo_ok else 'no'),
            'motivo_opencv': motivo_opencv,
            'motivo_yolo': motivo_yolo,
        })

    total = len(filas)
    aciertos_opencv = sum(f['opencv'] == 'si' for f in filas)
    aciertos_yolo = sum(f['yolo'] == 'si' for f in filas)
    solo_yolo = sum(f['opencv'] == 'no' and f['yolo'] == 'si' for f in filas)
    solo_opencv = sum(f['opencv'] == 'si' and f['yolo'] == 'no' for f in filas)

    args.salida.mkdir(parents=True, exist_ok=True)
    with (args.salida / 'comparacion_separacion.csv').open(
            'w', newline='', encoding='utf-8') as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=list(filas[0]))
        escritor.writeheader()
        escritor.writerows(filas)
    resumen = {
        'carpeta': str(args.fotografias.resolve()),
        'total': total,
        'separadas_opencv': aciertos_opencv,
        'separadas_yolo': aciertos_yolo if hay_detector else None,
        'solo_las_separa_yolo': solo_yolo if hay_detector else None,
        'solo_las_separa_opencv': solo_opencv if hay_detector else None,
        'modelo': str(RUTA_MODELO) if hay_detector else None,
        'alcance': 'separacion_de_filas_no_reconocimiento_de_cifras',
    }
    (args.salida / 'resumen_separacion.json').write_text(
        json.dumps(resumen, indent=2, ensure_ascii=False), encoding='utf-8')

    print(f'Fotografías evaluadas: {total}')
    print(f'Separadas por OpenCV:  {aciertos_opencv} de {total}')
    if hay_detector:
        print(f'Separadas por YOLO:    {aciertos_yolo} de {total}')
        print(f'  Recupera {solo_yolo} que OpenCV no separaba.')
        print(f'  Pierde {solo_opencv} que OpenCV sí separaba.')
        if solo_opencv > solo_yolo:
            print('\nEl detector separa menos fotos que el método actual. '
                  'No lo dejes activo:\nretira o renombra el archivo del modelo.')
    print(f'\nInforme en: {args.salida.resolve()}')
    print('Esta medición es de separación, no de exactitud de lectura.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
