"""Entrenar el detector de filas a partir del conjunto ya preparado.

Parte de un modelo YOLO preentrenado y lo ajusta a una sola clase: la fila de
cifras de una suma vertical. Entrena en CPU; con pocas imágenes el resultado
debe comprobarse con tools/comparar_separacion.py antes de usarlo en la web.

Terminar el entrenamiento no acredita RNF-02. Solo la comparación sobre
fotografías no usadas para entrenar indica si el detector mejora la
separación actual.

    python tools/preparar_dataset_yolo.py local_ocr/pruebas
    python tools/entrenar_yolo.py
    python tools/entrenar_yolo.py --epocas 120 --base yolov8s.pt
"""
from pathlib import Path
import argparse
import shutil
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--datos', type=Path,
                        default=Path('local_yolo/dataset/data.yaml'))
    parser.add_argument('--base', default='yolov8n.pt',
                        help='Modelo preentrenado de partida. La primera vez se descarga.')
    parser.add_argument('--epocas', type=int, default=80)
    parser.add_argument('--tamano', type=int, default=640,
                        help='Lado de la imagen de entrenamiento en píxeles.')
    parser.add_argument('--lote', type=int, default=4)
    parser.add_argument('--destino', type=Path, default=Path('local_yolo/separador.pt'),
                        help='Dónde se copia el mejor modelo al terminar.')
    parser.add_argument('--conservar', action='store_true',
                        help='No sobrescribir un modelo existente en --destino.')
    args = parser.parse_args()

    if not args.datos.is_file():
        parser.exit(1, f'Falta {args.datos}. Ejecuta antes '
                       'tools/preparar_dataset_yolo.py.\n')
    if args.conservar and args.destino.is_file():
        parser.exit(1, f'Ya existe {args.destino} y se pidió conservarlo.\n')
    try:
        from ultralytics import YOLO
    except ImportError:
        parser.exit(1, 'Falta ultralytics. Instala con: '
                       'python -m pip install -r requirements-yolo.txt\n')

    print(f'Entrenando desde {args.base} con {args.datos}.')
    print('En CPU puede tardar bastante. No cierres la terminal.\n', flush=True)
    # Ruta absoluta: con una relativa, ultralytics escribe en runs/ del proyecto.
    registros = Path('local_yolo/entrenamientos').resolve()
    modelo = YOLO(args.base)
    resultado = modelo.train(
        data=str(args.datos.resolve()),
        epochs=args.epocas,
        imgsz=args.tamano,
        batch=args.lote,
        device='cpu',
        project=str(registros),
        name='separador',
        exist_ok=False,
        seed=7,
        patience=30,
        # La hoja puede estar inclinada o desplazada al fotografiarla.
        degrees=12.0,
        translate=0.12,
        scale=0.35,
        shear=4.0,
        # Una suma vertical no se refleja ni se recombina con otra hoja.
        fliplr=0.0,
        flipud=0.0,
        mosaic=0.0,
        erasing=0.0,
        verbose=True,
    )

    mejor = Path(resultado.save_dir) / 'weights' / 'best.pt'
    if not mejor.is_file():
        parser.exit(1, f'El entrenamiento no dejó pesos en {mejor}.\n')
    args.destino.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(mejor, args.destino)
    print(f'\nModelo guardado en: {args.destino.resolve()}')
    print('La web lo usará en el próximo arranque del servidor.')
    print('Comprueba antes si mejora la separación actual:')
    print('  python tools/comparar_separacion.py local_ocr/evaluacion_ocr')
    return 0


if __name__ == '__main__':
    sys.exit(main())
