"""Separación de las tres filas de la suma mediante un detector YOLO.

Ruta alternativa a la separación con OpenCV de ``handwriting``. El detector
localiza las regiones de los dos sumandos y del resultado; no reconoce cifras,
no recibe el ejercicio seleccionado ni su resultado, y no guarda imágenes.

Si ultralytics no está instalado, si falta el archivo del modelo o si la
detección no encuentra exactamente tres filas, estas funciones devuelven
``None`` y la lectura continúa con el método anterior. Por eso un compañero
sin modelo entrenado conserva el comportamiento actual del proyecto.
"""
from functools import lru_cache
from pathlib import Path
from threading import Lock
import os

RECORTES = ('operando_a', 'operando_b', 'resultado')
RUTA_MODELO = os.environ.get('YOLO_SEPARADOR', 'local_yolo/separador.pt')
CONFIANZA_MINIMA = float(os.environ.get('YOLO_CONFIANZA', '0.25'))
# Una fila cuya altura sea muy inferior a la mediana suele ser un fragmento.
ALTURA_MINIMA_RELATIVA = 0.35
_deteccion_lock = Lock()


def ruta_modelo(ruta=None):
    """Ubicación del modelo entrenado, configurable con YOLO_SEPARADOR."""
    return Path(ruta or RUTA_MODELO)


def modelo_disponible(ruta=None):
    """Comprobar archivo y dependencia sin cargar el modelo en memoria.

    Se mira primero el archivo: así una instalación sin modelo entrenado no
    importa ultralytics, que al cargarse sustituye PIL.Image.open por una
    versión propia y cambiaría el trato de las fotografías dañadas.
    """
    if not ruta_modelo(ruta).is_file():
        return False
    try:
        import ultralytics  # noqa: F401
    except ImportError:
        return False
    return True


@lru_cache(maxsize=2)
def cargar_detector(ruta):
    """Cargar el detector una vez por proceso. ruta debe ser texto (cacheable)."""
    from ultralytics import YOLO

    return YOLO(str(ruta))


def ordenar_filas(cajas):
    """Asignar nombres por posición vertical: dos sumandos y un resultado.

    ``cajas`` es una lista de ``(x1, y1, x2, y2)``. Devuelve ``None`` cuando no
    hay exactamente tres filas utilizables, sin suponer cuál es el resultado.
    """
    utiles = [tuple(map(float, caja)) for caja in cajas
              if caja[2] > caja[0] and caja[3] > caja[1]]
    if len(utiles) != 3:
        return None
    alturas = sorted(caja[3] - caja[1] for caja in utiles)
    mediana = alturas[1]
    if alturas[0] < ALTURA_MINIMA_RELATIVA * mediana:
        return None
    ordenadas = sorted(utiles, key=lambda caja: caja[1] + caja[3])
    # Las filas de una suma vertical no se solapan entre sí.
    for superior, inferior in zip(ordenadas, ordenadas[1:]):
        if inferior[1] < superior[1] + 0.35 * (superior[3] - superior[1]):
            return None
    return {nombre: [int(round(v)) for v in caja]
            for nombre, caja in zip(RECORTES, ordenadas)}


def detectar_filas(imagen, ruta=None, confianza=None):
    """Devolver las cajas de las tres filas, o None si no se pudo detectar."""
    if not modelo_disponible(ruta):
        return None
    destino = str(ruta_modelo(ruta))
    umbral = CONFIANZA_MINIMA if confianza is None else confianza
    with _deteccion_lock:
        try:
            detector = cargar_detector(destino)
            salida = detector.predict(source=imagen, conf=umbral, verbose=False)
        except (ImportError, OSError, RuntimeError, ValueError):
            # Un fallo del detector nunca interrumpe la lectura: se usa OpenCV.
            return None
    if not salida:
        return None
    detecciones = getattr(salida[0], 'boxes', None)
    if detecciones is None or len(detecciones) == 0:
        return None
    try:
        cajas = [[float(v) for v in fila] for fila in detecciones.xyxy.tolist()]
    except (AttributeError, TypeError, ValueError):
        return None
    if len(cajas) > 3:
        # Conservar las tres detecciones más seguras antes de ordenarlas.
        try:
            confianzas = [float(v) for v in detecciones.conf.tolist()]
        except (AttributeError, TypeError, ValueError):
            return None
        cajas = [caja for _, caja in sorted(zip(confianzas, cajas),
                                            key=lambda par: par[0],
                                            reverse=True)[:3]]
    return ordenar_filas(cajas)


def _vista_de_region(imagen, cajas):
    """Imagen de apoyo que muestra solo las regiones detectadas."""
    from PIL import Image

    vista = Image.new('L', imagen.size, 255)
    gris = imagen.convert('L')
    for x1, y1, x2, y2 in cajas.values():
        region = gris.crop((x1, y1, x2, y2))
        vista.paste(region, (x1, y1))
    return vista


def separar_con_yolo(imagen, ruta=None, confianza=None):
    """Preparar los recortes con el detector, conservando el contrato previo.

    Devuelve ``(imagen, vista, recortes, cajas, angulo)`` igual que la
    separación con OpenCV, o ``None`` para que la lectura use ese método.
    El ángulo es 0.0: el detector localiza las filas sin enderezar la hoja.
    """
    cajas = detectar_filas(imagen, ruta, confianza)
    if cajas is None:
        return None
    # Mismos márgenes, normalización de iluminación y bordes que la ruta tenue,
    # para que el modelo de lectura reciba recortes comparables.
    from .handwriting import _recortes_con_contraste

    try:
        recortes, ampliadas = _recortes_con_contraste(imagen, cajas)
    except (OSError, ValueError, ZeroDivisionError):
        return None
    return imagen, _vista_de_region(imagen, cajas), recortes, ampliadas, 0.0
