"""Lectura experimental de una suma vertical azul, sin llevadas anotadas.

No recibe el ejercicio esperado ni calcula su respuesta. La web procesa la foto
en memoria. El modelo se carga una vez por proceso y las inferencias se serializan.
"""
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from threading import Lock
import math
import os
import re

MODELO = 'microsoft/trocr-small-handwritten'
REVISION_MODELO = 'b4648cfa171985a6745f37ddd637e98c0da958ac'
MAX_BYTES = 5 * 1024 * 1024
CAMPOS = ('operand_a', 'operand_b', 'written_result')
RECORTES = ('operando_a', 'operando_b', 'resultado')
_inference_lock = Lock()


class PhotoNotReadable(ValueError):
    """La foto no permite separar una suma dentro del alcance del prototipo."""


class ReaderUnavailable(RuntimeError):
    """Faltan dependencias, el modelo o los recursos para ejecutar la lectura."""


class ReaderBusy(RuntimeError):
    """El proceso ya está atendiendo otra fotografía."""


def quitar_ruido(mask, area_minima=12):
    import cv2
    import numpy as np

    _, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    conservar = stats[:, cv2.CC_STAT_AREA] >= area_minima
    conservar[0] = False
    return np.uint8(conservar[labels]) * 255


def agrupar_componentes(componentes, distancia):
    import numpy as np

    grupos = []
    for componente in sorted(componentes, key=lambda c: c[2] + c[4] / 2):
        centro = componente[2] + componente[4] / 2
        if grupos:
            centro_grupo = np.mean([c[2] + c[4] / 2 for c in grupos[-1]])
        if not grupos or abs(centro - centro_grupo) > distancia:
            grupos.append([])
        grupos[-1].append(componente)
    return grupos


def preparar_suma(fotografia):
    """Separar filas desde una ruta o un archivo abierto, sin guardar imágenes."""
    import cv2
    import numpy as np
    from PIL import Image, ImageOps

    if isinstance(fotografia, (str, os.PathLike)):
        ruta = Path(fotografia)
        if ruta.stat().st_size > MAX_BYTES:
            raise PhotoNotReadable('La fotografía supera los 5 MB.')
        contenido = ruta.read_bytes()
    else:
        fotografia.seek(0)
        contenido = fotografia.read(MAX_BYTES + 1)
        fotografia.seek(0)
    if len(contenido) > MAX_BYTES:
        raise PhotoNotReadable('La fotografía supera los 5 MB.')
    try:
        with Image.open(BytesIO(contenido)) as archivo:
            if archivo.format not in ('JPEG', 'PNG'):
                raise PhotoNotReadable('Selecciona una imagen JPG o PNG.')
            if archivo.width * archivo.height > 20_000_000:
                raise PhotoNotReadable('La fotografía supera los 20 megapíxeles.')
            imagen = ImageOps.exif_transpose(archivo).convert('RGB')
    except (OSError, Image.DecompressionBombError) as exc:
        raise PhotoNotReadable('La fotografía está dañada o no se puede leer.') from exc
    imagen.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
    rgb = np.asarray(imagen, dtype=np.int16)
    azul = ((rgb[:, :, 2] - rgb[:, :, 0] > 35)
            & (rgb[:, :, 2] - rgb[:, :, 1] > 15)
            & (rgb[:, :, 0] < 190))
    mask = quitar_ruido(np.uint8(azul) * 255)
    ys, xs = np.where(mask)
    if len(xs) < 100:
        raise PhotoNotReadable('No hay suficiente tinta azul legible para este ensayo.')
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
        raise PhotoNotReadable('No pude localizar una línea de suma suficientemente clara.')
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
        raise PhotoNotReadable('No pude aislar el signo +. Usa una sola suma vertical clara.')
    indice_signo = min(signos)[1]
    mask[labels == indice_signo] = 0
    mask[inicio:fin] = 0
    mask = quitar_ruido(mask, area_minima=12)
    _, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    componentes = [(i, *map(int, s)) for i, s in enumerate(stats[1:], 1)]
    if not componentes:
        raise PhotoNotReadable('No quedan trazos legibles después de separar la línea.')
    altura_mediana = float(np.median([c[4] for c in componentes]))
    componentes = [c for c in componentes if c[4] >= max(8, .3 * altura_mediana)]
    distancia = max(8, .6 * altura_mediana)
    arriba = agrupar_componentes([c for c in componentes if c[2] + c[4] <= inicio], distancia)
    abajo = agrupar_componentes([c for c in componentes if c[2] >= fin], distancia)
    if len(arriba) != 2 or len(abajo) != 1:
        raise PhotoNotReadable('No pude separar dos operandos y un resultado. Revisa la fotografía.')

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


@lru_cache(maxsize=1)
def cargar_modelo(modelo=MODELO, local_files_only=False):
    import torch
    from transformers import TrOCRProcessor, VisionEncoderDecoderModel

    torch.set_num_threads(min(4, os.cpu_count() or 1))
    opciones = {'local_files_only': local_files_only}
    if modelo == MODELO:
        opciones['revision'] = REVISION_MODELO
    procesador = TrOCRProcessor.from_pretrained(modelo, use_fast=False, **opciones)
    reconocedor = VisionEncoderDecoderModel.from_pretrained(
        modelo, weights_only=True, use_safetensors=False, **opciones,
    ).eval()
    return procesador, reconocedor


def normalizar_lecturas(lecturas_crudas):
    propuesta = {}
    for campo in CAMPOS:
        texto = lecturas_crudas[campo]
        compacto = ''.join(texto.split())
        limite = 4 if campo == 'written_result' else 3
        valido = re.fullmatch(r'[0-9]{1,' + str(limite) + r'}', compacto)
        propuesta[campo] = int(compacto) if valido else None
    return propuesta


def reconocer_recortes(recortes, modelo=MODELO, *, local_files_only=False,
                       esperar=True):
    """Transcribir los trazos. Los errores de lectura permanecen editables."""
    if not _inference_lock.acquire(blocking=esperar):
        raise ReaderBusy('El lector está ocupado. Espera un momento y vuelve a cargar la foto.')
    try:
        import torch
        procesador, reconocedor = cargar_modelo(modelo, local_files_only)
        lecturas_crudas = {}
        for campo, nombre in zip(CAMPOS, RECORTES):
            valores = procesador(images=recortes[nombre], return_tensors='pt').pixel_values
            with torch.inference_mode():
                ids = reconocedor.generate(valores, max_new_tokens=12, num_beams=3)
            lecturas_crudas[campo] = procesador.batch_decode(ids, skip_special_tokens=True)[0]
        propuesta = normalizar_lecturas(lecturas_crudas)
        return {
            'estado': ('pendiente_de_confirmacion'
                       if all(v is not None for v in propuesta.values())
                       else 'lectura_pendiente'),
            'source': 'trocr-small-handwritten',
            'propuesta': propuesta,
            'lecturas_crudas': lecturas_crudas,
        }
    except (ImportError, OSError, RuntimeError, ValueError) as exc:
        raise ReaderUnavailable('No se pudo iniciar o ejecutar el lector.') from exc
    finally:
        _inference_lock.release()


def leer_fotografia(fotografia, modelo=MODELO):
    """Usar únicamente el modelo ya descargado; la web no inicia descargas."""
    try:
        _, _, recortes, _, _ = preparar_suma(fotografia)
    except PhotoNotReadable as exc:
        return {
            'estado': 'lectura_pendiente',
            'source': 'trocr-small-handwritten',
            'propuesta': dict.fromkeys(CAMPOS),
            'can_confirm': False,
            'mensaje': f'Lectura pendiente. {exc} Toma otra fotografía y vuelve a cargarla.',
        }
    except ImportError as exc:
        raise ReaderUnavailable('Faltan las dependencias de preparación de imágenes.') from exc

    lectura = reconocer_recortes(recortes, modelo, local_files_only=True, esperar=False)
    lectura.pop('lecturas_crudas')
    lectura['can_confirm'] = any(v is not None for v in lectura['propuesta'].values())
    if lectura['estado'] == 'pendiente_de_confirmacion':
        lectura['mensaje'] = 'Lectura lista. Revisa los tres números con tu fotografía y confírmalos.'
    elif lectura['can_confirm']:
        lectura['mensaje'] = ('Lectura incompleta. Revisa los números propuestos y completa '
                              'los campos vacíos con lo que aparece en tu fotografía.')
    else:
        lectura['mensaje'] = ('Lectura pendiente. No pude leer los números. '
                              'Toma una fotografía más clara y vuelve a cargarla.')
    return lectura
