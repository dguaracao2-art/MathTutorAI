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
            if archivo.format not in ('JPEG', 'PNG', 'MPO'):
                raise PhotoNotReadable('Selecciona una imagen JPG o PNG.')
            if archivo.width * archivo.height > 20_000_000:
                raise PhotoNotReadable('La fotografía supera los 20 megapíxeles.')
            # JPEG de cámara con imagen auxiliar: usar solo la imagen principal.
            archivo.seek(0)
            imagen = ImageOps.exif_transpose(archivo).convert('RGB')
    except (OSError, Image.DecompressionBombError) as exc:
        raise PhotoNotReadable('La fotografía está dañada o no se puede leer.') from exc
    imagen.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
    try:
        return _separar_suma(imagen, 35, 15, 190)
    except PhotoNotReadable:
        # La máscara débil localiza la tinta tenue; el OCR conserva el original.
        try:
            return _separar_suma(imagen, 15, 8, 220, recortar=True)
        except PhotoNotReadable:
            # El papel azulado puede cumplir el criterio de color de la tinta.
            # Otsu exige además un trazo oscuro; no usa valores del ejercicio.
            return _separar_suma(imagen, 15, 8, 220, limpiar_fondo=True)


def _separar_suma(imagen, contraste_rojo, contraste_verde, rojo_maximo,
                  recortar=False, limpiar_fondo=False):
    import cv2
    import numpy as np
    from PIL import Image

    rgb = np.asarray(imagen, dtype=np.int16)
    azul = ((rgb[:, :, 2] - rgb[:, :, 0] > contraste_rojo)
            & (rgb[:, :, 2] - rgb[:, :, 1] > contraste_verde)
            & (rgb[:, :, 0] < rojo_maximo))
    if limpiar_fondo:
        gris = cv2.cvtColor(np.asarray(imagen), cv2.COLOR_RGB2GRAY)
        umbral, _ = cv2.threshold(gris, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        azul &= gris <= umbral
    mask = quitar_ruido(np.uint8(azul) * 255)
    if np.count_nonzero(mask) < 100:
        raise PhotoNotReadable('No hay suficiente tinta azul legible para este ensayo.')
    lineas = cv2.HoughLinesP(mask, 1, np.pi / 180, threshold=25,
                             minLineLength=max(30, int(min(mask.shape) * .035)),
                             maxLineGap=10)
    candidatas = []
    if lineas is not None:
        for x1, y1, x2, y2 in np.asarray(lineas).reshape(-1, 4):
            dx, dy = int(x2 - x1), int(y2 - y1)
            if dx and abs(dy / dx) <= math.tan(math.radians(12)):
                candidatas.append((dx * dx + dy * dy, math.degrees(math.atan(dy / dx)),
                                   (int(x1), int(y1), int(x2), int(y2))))
    if not candidatas:
        raise PhotoNotReadable('No pude localizar una línea de suma suficientemente clara.')
    largo_cuadrado, angulo, linea = max(candidatas)
    alto, ancho = mask.shape
    if recortar:
        longitud = math.sqrt(largo_cuadrado)
        x1, y1, x2, y2 = linea
        xmin = max(0, int(min(x1, x2) - .65 * longitud))
        xmax = min(ancho, int(max(x1, x2) + .5 * longitud))
        ymin = max(0, int(min(y1, y2) - 2.25 * longitud))
        ymax = min(alto, int(max(y1, y2) + .8 * longitud))
        tinta_tenue = ((rgb[:, :, 2] - rgb[:, :, 0] > 15)
                      & (rgb[:, :, 2] - rgb[:, :, 1] > 8)
                      & (rgb[:, :, 0] < 220))
        if tinta_tenue[ymin:ymax, xmin:xmax].mean() > .12:
            tinta_tenue = ((rgb[:, :, 2] - rgb[:, :, 0] > 20)
                          & (rgb[:, :, 2] - rgb[:, :, 1] > 8)
                          & (rgb[:, :, 0] < 220))
        zona = np.zeros_like(mask)
        zona[ymin:ymax, xmin:xmax] = np.uint8(tinta_tenue[ymin:ymax, xmin:xmax]) * 255
        mask = quitar_ruido(zona)
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
        margen_linea = max(20, int(.06 * longitud)) if recortar else 2
        if area < 30 or y <= corte_superior or y + h > inicio + margen_linea:
            continue
        if recortar and x >= min(linea[0], linea[2]):
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
    altura_signo = int(stats[indice_signo, cv2.CC_STAT_HEIGHT])
    mask[labels == indice_signo] = 0
    if recortar:
        trazos_horizontales = cv2.morphologyEx(
            mask, cv2.MORPH_OPEN,
            np.ones((1, max(40, int(longitud * .3))), dtype=np.uint8),
        )
        mask[trazos_horizontales > 0] = 0
    mask[inicio:fin] = 0
    mask = quitar_ruido(mask, area_minima=12)
    _, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    componentes = [(i, *map(int, s)) for i, s in enumerate(stats[1:], 1)]
    if not componentes:
        raise PhotoNotReadable('No quedan trazos legibles después de separar la línea.')
    if recortar:
        trazos_principales = [c[4] for c in componentes if c[4] >= longitud * .1]
        if not trazos_principales:
            raise PhotoNotReadable('No hay dígitos legibles junto a la línea.')
        altura_mediana = float(np.median(trazos_principales))
        componentes = [c for c in componentes if c[4] >= max(8, .18 * altura_mediana)]
    else:
        altura_mediana = float(np.median([c[4] for c in componentes]))
        componentes = [c for c in componentes if c[4] >= max(8, .3 * altura_mediana)]
    distancia = max(8, .9 * altura_signo, (.95 if recortar else .6) * altura_mediana)
    arriba = agrupar_componentes([c for c in componentes if c[2] + c[4] <= inicio], distancia)
    abajo = agrupar_componentes([c for c in componentes if c[2] >= fin], distancia)
    if len(arriba) != 2 or len(abajo) != 1:
        raise PhotoNotReadable('No pude separar dos operandos y un resultado. Revisa la fotografía.')

    cajas = {}
    ids_validos = [c[0] for grupo in arriba + abajo for c in grupo]
    mask = np.uint8(np.isin(labels, ids_validos)) * 255
    for nombre, grupo in zip(('operando_a', 'operando_b', 'resultado'), arriba + abajo):
        x1 = min(c[1] for c in grupo)
        y1 = min(c[2] for c in grupo)
        x2 = max(c[1] + c[3] for c in grupo)
        y2 = max(c[2] + c[4] for c in grupo)
        if y2 - y1 < .4 * altura_signo:
            raise PhotoNotReadable('No hay suficientes trazos para leer una fila completa.')
        cajas[nombre] = [x1, y1, x2, y2]
    if recortar:
        recortes, cajas = _recortes_con_contraste(imagen, cajas)
    else:
        # Con tinta bien aislada, quitar también la cuadrícula del cuaderno.
        from PIL import ImageOps
        recortes = {}
        for nombre, (x1, y1, x2, y2) in cajas.items():
            limpio = _limpiar_fila_binaria(mask[y1:y2, x1:x2])
            recorte = Image.fromarray(255 - limpio)
            recortes[nombre] = ImageOps.expand(recorte, border=15, fill='white').convert('RGB')
    return imagen, Image.fromarray(255 - mask), recortes, cajas, angulo


def _limpiar_fila_binaria(mask):
    """Quitar fragmentos aislados pequeños sin alterar componentes conservados."""
    import cv2
    import numpy as np

    limpio = mask.copy()
    _, labels, stats, _ = cv2.connectedComponentsWithStats(limpio, connectivity=8)
    if len(stats) <= 1:
        return mask
    altura = max(stats[1:, cv2.CC_STAT_HEIGHT])
    area = max(stats[1:, cv2.CC_STAT_AREA])
    conservar = ((stats[:, cv2.CC_STAT_HEIGHT] >= .2 * altura)
                 | (stats[:, cv2.CC_STAT_AREA] >= .5 * area))
    conservar[0] = False
    limpio = np.uint8(conservar[labels]) * 255
    ys, xs = np.where(limpio)
    if not len(xs):
        return mask
    return limpio[ys.min():ys.max() + 1, xs.min():xs.max() + 1]


def _recortes_con_contraste(imagen, cajas):
    """Conservar trazos tenues que la máscara puede perder al segmentar."""
    from PIL import ImageOps

    alturas = sorted(caja[3] - caja[1] for caja in cajas.values())
    margen = max(4, round(.3 * alturas[len(alturas) // 2]))
    separacion = (cajas['operando_a'][3] + cajas['operando_b'][1]) // 2
    recortes, ampliadas = {}, {}
    for nombre in RECORTES:
        x1, y1, x2, y2 = cajas[nombre]
        superior = max(0, y1 - margen)
        inferior = min(imagen.height, y2 + margen)
        if nombre == 'operando_a':
            inferior = min(inferior, separacion)
        elif nombre == 'operando_b':
            superior = max(superior, separacion)
            inferior = y2  # No incluir la línea de suma.
        else:
            superior = y1
        caja = [max(0, x1 - margen), superior,
                min(imagen.width, x2 + margen), inferior]
        recorte = _normalizar_iluminacion_fila(imagen.crop(caja))
        recortes[nombre] = ImageOps.expand(recorte, border=15, fill='white').convert('RGB')
        ampliadas[nombre] = caja
    return recortes, ampliadas


def _normalizar_iluminacion_fila(recorte):
    """Uniformar el papel de una fila tenue conservando sus trazos originales."""
    import cv2
    import numpy as np
    from PIL import Image

    gris = np.asarray(recorte.convert('L'))
    # El cierre estima el fondo local alrededor de los trazos oscuros.
    # Dividir por él reduce sombras suaves; el autocontraste global anterior
    # también oscurecía la cuadrícula. Esta ruta solo se usa tras aislar filas
    # con tinta tenue, sin recibir números ni resultados del ejercicio.
    fondo = cv2.morphologyEx(gris, cv2.MORPH_CLOSE, np.ones((31, 31), np.uint8))
    normalizada = cv2.divide(gris, np.maximum(fondo, 1), scale=255)
    return Image.fromarray(normalizada)


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
    # La tarea transcribe números; nunca recibe la respuesta del ejercicio.
    permitidos = {indice for token, indice in procesador.tokenizer.get_vocab().items()
                  if re.fullmatch(r'[▁Ġ0-9]+', token)}
    permitidos.add(procesador.tokenizer.eos_token_id)
    reconocedor.generation_config.suppress_tokens = sorted(
        set(range(reconocedor.config.decoder.vocab_size)) - permitidos
    )
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
        valores = procesador(images=[recortes[nombre] for nombre in RECORTES],
                             return_tensors='pt').pixel_values
        with torch.inference_mode():
            ids = reconocedor.generate(valores, max_new_tokens=12, num_beams=3)
        lecturas_crudas = dict(zip(
            CAMPOS, procesador.batch_decode(ids, skip_special_tokens=True)
        ))
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


def leer_fotografia(fotografia, modelo=MODELO, *, incluir_diagnostico=False):
    """Usar únicamente el modelo ya descargado; la web no inicia descargas."""
    try:
        _, _, recortes, _, _ = preparar_suma(fotografia)
    except PhotoNotReadable as exc:
        return {
            'estado': 'lectura_pendiente',
            'etapa': 'separacion',
            'source': 'trocr-small-handwritten',
            'propuesta': dict.fromkeys(CAMPOS),
            'can_confirm': False,
            'mensaje': f'Lectura pendiente. {exc} Toma otra fotografía y vuelve a cargarla.',
        }
    except ImportError as exc:
        raise ReaderUnavailable('Faltan las dependencias de preparación de imágenes.') from exc

    lectura = reconocer_recortes(recortes, modelo, local_files_only=True, esperar=False)
    if not incluir_diagnostico:
        lectura.pop('lecturas_crudas')
    lectura['etapa'] = 'reconocimiento'
    # La geometría ya se validó; permitir completar incluso tres campos vacíos.
    lectura['can_confirm'] = True
    if lectura['estado'] == 'pendiente_de_confirmacion':
        lectura['mensaje'] = 'Lectura lista. Revisa los tres números con tu fotografía y confírmalos.'
    elif any(v is not None for v in lectura['propuesta'].values()):
        lectura['mensaje'] = ('Lectura incompleta. Revisa los números propuestos y completa '
                              'los campos vacíos con lo que aparece en tu fotografía.')
    else:
        lectura['mensaje'] = ('No pude proponer los números. Mira tu fotografía y completa '
                              'los tres campos antes de confirmar, o toma otra foto.')
    return lectura
