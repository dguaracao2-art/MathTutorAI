"""Crear copias PNG de la imagen principal para diagnosticar formatos JPEG/MPO.

No ejecuta OCR, no cambia el lector y no modifica archivos originales.
Las copias son un ensayo con entrada normalizada, no una nueva prueba independiente.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import shutil
import tempfile

from PIL import Image, ImageOps


def normalizar(origen, destino):
    origen, destino = Path(origen).resolve(), Path(destino).resolve()
    if not origen.is_dir():
        raise ValueError('No existe la carpeta de origen.')
    if destino.exists():
        raise ValueError('El destino ya existe. Usa una carpeta nueva para no sobrescribir resultados.')
    if origen == destino or origen in destino.parents:
        raise ValueError('Utiliza una carpeta de destino fuera de la carpeta original.')
    with (origen / 'referencia_ocr.csv').open(encoding='utf-8-sig', newline='') as f:
        primera = f.readline()
        f.seek(0)
        reader = csv.DictReader(f, delimiter=';' if ';' in primera else ',')
        cabecera = ['archivo', 'operand_a', 'operand_b', 'written_result']
        if reader.fieldnames != cabecera:
            raise ValueError('La referencia debe contener: ' + ','.join(cabecera))
        filas = list(reader)
    if not filas:
        raise ValueError('La referencia esta vacia.')
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporal = Path(tempfile.mkdtemp(prefix='normalizando_', dir=destino.parent))
    registros, nuevas, nombres = [], [], set()
    try:
        for row in filas:
            nombre = row['archivo']
            if not nombre or '/' in nombre or '\\' in nombre:
                raise ValueError('Nombre de foto invalido en la referencia.')
            foto = origen / nombre
            if foto.resolve().parent != origen or foto.suffix.lower() not in ('.jpeg', '.jpg', '.png'):
                raise ValueError(f'Foto no admitida: {nombre}')
            if foto.stat().st_size > 5 * 1024 * 1024:
                raise ValueError(f'{nombre}: supera los 5 MB.')
            nuevo = foto.stem + '.png'
            if nuevo.casefold() in nombres:
                raise ValueError(f'Nombre de salida repetido: {nuevo}')
            nombres.add(nuevo.casefold())
            with Image.open(foto) as im:
                formato = im.format
                if formato not in ('JPEG', 'PNG', 'MPO'):
                    raise ValueError(f'{nombre}: formato interno no admitido: {formato}')
                if im.width * im.height > 20_000_000:
                    raise ValueError(f'{nombre}: supera los 20 megapixeles.')
                frames = getattr(im, 'n_frames', 1)
                im.seek(0)
                principal = ImageOps.exif_transpose(im).convert('RGB')
                principal.save(temporal / nuevo, format='PNG')
            if (temporal / nuevo).stat().st_size > 5 * 1024 * 1024:
                raise ValueError(f'{nuevo}: el PNG supera 5 MB; no se reducira ni descartara automaticamente.')
            registros.append({'original': nombre, 'copia': nuevo,
                              'formato_original': formato, 'imagenes_internas': frames,
                              'imagen_seleccionada': 0,
                              'sha256_original': hashlib.sha256(foto.read_bytes()).hexdigest(),
                              'sha256_copia': hashlib.sha256((temporal / nuevo).read_bytes()).hexdigest()})
            nuevas.append({**row, 'archivo': nuevo})
        with (temporal / 'referencia_ocr.csv').open('w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=cabecera)
            writer.writeheader()
            writer.writerows(nuevas)
        (temporal / 'normalizacion.json').write_text(json.dumps({
            'tipo': 'ensayo_con_entrada_normalizada',
            'nota': 'No es un conjunto independiente del original. No se ejecuto OCR.',
            'transformacion': 'Imagen principal, orientacion EXIF y RGB a PNG; sin redimensionar.',
            'archivos': registros,
        }, ensure_ascii=False, indent=2), encoding='utf-8')
        temporal.rename(destino)
    except Exception:
        shutil.rmtree(temporal, ignore_errors=True)
        raise
    formatos = {}
    for r in registros:
        clave = r['formato_original']
        formatos[clave] = formatos.get(clave, 0) + 1
    return len(nuevas), formatos


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('origen', type=Path)
    parser.add_argument('destino', type=Path)
    args = parser.parse_args()
    try:
        cantidad, formatos = normalizar(args.origen, args.destino)
    except (OSError, ValueError, Image.DecompressionBombError) as exc:
        parser.exit(1, f'No se completo la normalizacion: {exc}\n')
    print('Formatos internos originales:', formatos)
    print(f'Copias PNG creadas: {cantidad}. Destino: {args.destino}')
    print('Referencia copiada con nombres .png; originales y resultados anteriores conservados.')
    print('No se ejecuto OCR. Las copias sirven para un ensayo, no para certificar RNF-02.')


if __name__ == '__main__':
    main()
