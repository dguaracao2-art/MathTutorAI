"""Prototipo de lectura de una suma vertical escrita con tinta azul.

Alcance de este ensayo: una suma, dos operandos, un resultado y una línea
separadora; sin llevadas manuscritas adicionales. Sin --reconocer solo prepara
recortes; con esa opción propone números pendientes de confirmación. No evalúa
la operación. Las coordenadas se calculan a partir de la imagen.
"""
from pathlib import Path
import argparse
import json
import math
import re
import os

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageOps


MODELO = 'microsoft/trocr-small-handwritten'
REVISION_MODELO = 'b4648cfa171985a6745f37ddd637e98c0da958ac'


def quitar_ruido(mask, area_minima=12):
    _, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    conservar = stats[:, cv2.CC_STAT_AREA] >= area_minima
    conservar[0] = False
    return np.uint8(conservar[labels]) * 255


def agrupar_componentes(componentes, distancia):
    grupos = []
    for componente in sorted(componentes, key=lambda c: c[2] + c[4] / 2):
        centro = componente[2] + componente[4] / 2
        if grupos:
            centro_grupo = np.mean([c[2] + c[4] / 2 for c in grupos[-1]])
        if not grupos or abs(centro - centro_grupo) > distancia:
            grupos.append([])
        grupos[-1].append(componente)
    return grupos


def preparar_suma(ruta):
    ruta = Path(ruta)
    if ruta.stat().st_size > 5 * 1024 * 1024:
        raise ValueError('La fotografía supera los 5 MB.')
    with Image.open(ruta) as archivo:
        if archivo.format not in ('JPEG', 'PNG'):
            raise ValueError('Selecciona una imagen JPG o PNG.')
        if archivo.width * archivo.height > 20_000_000:
            raise ValueError('La fotografía supera los 20 megapíxeles.')
        imagen = ImageOps.exif_transpose(archivo).convert('RGB')
    imagen.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
    rgb = np.asarray(imagen, dtype=np.int16)
    azul = ((rgb[:, :, 2] - rgb[:, :, 0] > 35)
            & (rgb[:, :, 2] - rgb[:, :, 1] > 15)
            & (rgb[:, :, 0] < 190))
    mask = quitar_ruido(np.uint8(azul) * 255)
    ys, xs = np.where(mask)
    if len(xs) < 100:
        raise ValueError('No hay suficiente tinta azul legible para este ensayo.')
    alto_tinta = int(ys.max() - ys.min() + 1)
    lineas = cv2.HoughLinesP(mask, 1, np.pi / 180, threshold=25,
                             minLineLength=max(40, int(alto_tinta * .25)),
                             maxLineGap=10)
    candidatas = []
    if lineas is not None:
        for x1, y1, x2, y2 in np.asarray(lineas).reshape(-1, 4):
            dx, dy = int(x2 - x1), int(y2 - y1)
            if dx and abs(dy / dx) <= math.tan(math.radians(12)):
                candidatas.append((dx * dx + dy * dy, math.degrees(math.atan(dy / dx))))
    if not candidatas:
        raise ValueError('No pude localizar una línea de suma suficientemente clara.')
    angulo = max(candidatas)[1]
    alto, ancho = mask.shape
    matriz = cv2.getRotationMatrix2D((ancho / 2, alto / 2), angulo, 1)
    mask = cv2.warpAffine(mask, matriz, (ancho, alto), flags=cv2.INTER_NEAREST)
    mask = quitar_ruido(mask)
    imagen = Image.fromarray(cv2.warpAffine(np.asarray(imagen), matriz,
                             (ancho, alto), borderValue=(255, 255, 255)))
    proyeccion = np.count_nonzero(mask, axis=1)
    centro_linea = int(np.argmax(proyeccion))
    umbral = proyeccion[centro_linea] * .55
    inicio, fin = centro_linea, centro_linea + 1
    while inicio > 0 and proyeccion[inicio - 1] >= umbral:
        inicio -= 1
    while fin < alto and proyeccion[fin] >= umbral:
        fin += 1

    # Localizar una cruz aislada a la izquierda de la segunda fila.
    _, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    superior = int(np.where(mask)[0].min())
    corte_superior = superior + (inicio - superior) * .25
    signos = []
    for indice, (x, y, w, h, area) in enumerate(stats[1:], 1):
        if area < 30 or y <= corte_superior or y + h > inicio + 2:
            continue
        if not .4 <= w / h <= 1.8:
            continue
        pieza = labels[y:y + h, x:x + w] == indice
        horizontal = pieza.sum(axis=1)
        vertical = pieza.sum(axis=0)
        if (horizontal.max() >= .65 * w and vertical.max() >= .65 * h
                and .15 * h <= horizontal.argmax() <= .85 * h
                and .15 * w <= vertical.argmax() <= .85 * w):
            signos.append((int(x), indice))
    if not signos:
        raise ValueError('No pude aislar el signo +. Usa una sola suma vertical clara.')
    indice_signo = min(signos)[1]
    mask[labels == indice_signo] = 0
    mask[inicio:fin] = 0
    mask = quitar_ruido(mask, area_minima=12)
    _, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    componentes = [(i, *map(int, s)) for i, s in enumerate(stats[1:], 1)]
    if not componentes:
        raise ValueError('No quedan trazos legibles después de separar la línea.')
    altura_mediana = float(np.median([c[4] for c in componentes]))
    componentes = [c for c in componentes if c[4] >= max(8, .3 * altura_mediana)]
    distancia = max(8, .6 * altura_mediana)
    arriba = agrupar_componentes([c for c in componentes if c[2] + c[4] <= inicio], distancia)
    abajo = agrupar_componentes([c for c in componentes if c[2] >= fin], distancia)
    if len(arriba) != 2 or len(abajo) != 1:
        raise ValueError('No pude separar dos operandos y un resultado. Revisa la fotografía.')

    recortes, cajas = {}, {}
    ids_validos = [c[0] for grupo in arriba + abajo for c in grupo]
    mask = np.uint8(np.isin(labels, ids_validos)) * 255
    for nombre, grupo in zip(('operando_a', 'operando_b', 'resultado'), arriba + abajo):
        x1 = min(c[1] for c in grupo)
        y1 = min(c[2] for c in grupo)
        x2 = max(c[1] + c[3] for c in grupo)
        y2 = max(c[2] + c[4] for c in grupo)
        caja = (x1, y1, x2, y2)
        seleccion = np.isin(labels[y1:y2, x1:x2], [c[0] for c in grupo])
        recorte = Image.fromarray(np.where(seleccion, 0, 255).astype(np.uint8)).convert('RGB')
        recortes[nombre] = ImageOps.expand(recorte, border=15, fill='white')
        cajas[nombre] = list(caja)
    return imagen, Image.fromarray(255 - mask), recortes, cajas, angulo


def reconocer_recortes(recortes, modelo=MODELO):
    """Proponer una transcripción; no compara ni corrige los números leídos."""
    import torch
    from transformers import TrOCRProcessor, VisionEncoderDecoderModel

    torch.set_num_threads(min(4, os.cpu_count() or 1))
    opciones = {'revision': REVISION_MODELO} if modelo == MODELO else {}
    procesador = TrOCRProcessor.from_pretrained(modelo, use_fast=False, **opciones)
    reconocedor = VisionEncoderDecoderModel.from_pretrained(
        modelo, weights_only=True, **opciones).eval()
    propuesta = {}
    lecturas_crudas = {}
    campos = ('operand_a', 'operand_b', 'written_result')
    for campo, recorte in zip(campos, recortes.values()):
        valores = procesador(images=recorte, return_tensors='pt').pixel_values
        with torch.inference_mode():
            ids = reconocedor.generate(valores, max_new_tokens=12, num_beams=3)
        texto = procesador.batch_decode(ids, skip_special_tokens=True)[0]
        lecturas_crudas[campo] = texto
        # Solo normalizamos espacios. Las letras y los símbolos no se borran
        # para convertir una lectura ambigua en un número aparentemente válido.
        compacto = ''.join(texto.split())
        limite_cifras = 4 if campo == 'written_result' else 3
        valido = re.fullmatch(r'[0-9]{1,' + str(limite_cifras) + r'}', compacto)
        propuesta[campo] = int(compacto) if valido else None
    return {
        'estado': 'pendiente_de_confirmacion' if all(v is not None for v in propuesta.values()) else 'lectura_pendiente',
        'source': 'trocr-small-handwritten',
        'propuesta': propuesta,
        'lecturas_crudas': lecturas_crudas,
    }


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
