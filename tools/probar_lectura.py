"""Prueba por terminal del mismo lector usado por la página de MathTutor AI."""
from pathlib import Path
import argparse
import json
import re
import sys

from PIL import Image, ImageDraw

# Permite ejecutar: python tools/probar_lectura.py ...
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tutoring.services.handwriting import MODELO, preparar_suma, reconocer_recortes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('fotografia', type=Path)
    parser.add_argument('--salida', type=Path)
    parser.add_argument('--reconocer', action='store_true',
                        help='Ejecutar TrOCR después de preparar la fotografía.')
    parser.add_argument('--modelo', default=MODELO,
                        help='Identificador del modelo o directorio local compatible.')
    args = parser.parse_args()
    try:
        imagen, mascara, recortes, cajas, angulo = preparar_suma(args.fotografia)
    except (OSError, ValueError, Image.DecompressionBombError) as exc:
        parser.exit(1, f'Lectura pendiente: {exc}\n')
    nombre = re.sub(r'[^A-Za-z0-9_-]+', '_', args.fotografia.stem)
    destino = args.salida or Path('local_ocr/salidas') / nombre
    destino.mkdir(parents=True, exist_ok=True)
    mascara.save(destino / 'mascara.png')
    dibujo = ImageDraw.Draw(imagen)
    for nombre, recorte in recortes.items():
        recorte.save(destino / f'{nombre}.png')
        dibujo.rectangle(cajas[nombre], outline='red', width=2)
    imagen.save(destino / 'ubicaciones.png')
    (destino / 'preparacion.json').write_text(json.dumps({
        'estado': 'recortes_pendientes_de_reconocimiento',
        'alcance': 'prototipo_tinta_azul_sin_llevadas_visibles',
        'angulo_grados': round(angulo, 3), 'cajas': cajas,
    }, indent=2), encoding='utf-8')
    print('Preparación completada: tres recortes pendientes de reconocimiento.')
    print(f'Salida: {destino.resolve()}')
    if args.reconocer:
        print('Iniciando TrOCR. La primera ejecución puede descargar el modelo.', flush=True)
        try:
            lectura = reconocer_recortes(recortes, args.modelo)
        except (ImportError, OSError, RuntimeError, ValueError) as exc:
            parser.exit(1, f'No se completó el reconocimiento: {exc}\nLos recortes preparados siguen disponibles.\n')
        (destino / 'lectura.json').write_text(
            json.dumps(lectura, indent=2, ensure_ascii=False), encoding='utf-8')
        print(json.dumps(lectura, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
