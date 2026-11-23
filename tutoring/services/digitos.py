"""Lectura cifra a cifra, como alternativa a transcribir la fila como texto.

El lector basado en TrOCR trata cada fila como una línea de texto libre y
puede devolver más caracteres de los que hay escritos. Medido sobre las 50
fotografías del ensayo, veinte lecturas se descartaron por traer un dígito de
más, casi siempre un "1" nacido de un trazo vertical: el signo +, la raya de
la suma o una línea de la cuadrícula.

Aquí el problema se plantea distinto. Primero se separan las cifras una por
una con componentes conexas, y luego cada recorte se clasifica en una de diez
clases. Un clasificador no puede insertar un carácter: devuelve exactamente
una clase por recorte. Ese modo de fallo desaparece por construcción, y a
cambio aparece otro distinto —que la separación junte o parta una cifra—, que
es más fácil de ver y de corregir.

Medido con un modelo entrenado sobre 95 cifras de 14 fotografías y evaluado
sobre 7 fotografías que no intervinieron en el entrenamiento: 6 de 7 lecturas
completas y 20 de 21 campos.

El clasificador es opcional. Sin el archivo del modelo, nada de esto se
activa y la lectura sigue por el camino de siempre.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
MODELO_POR_OMISION = RAIZ / 'local_yolo' / 'clasificador_digitos.pt'
# Lado del recorte normalizado que recibe la red.
LADO = 28
# Altura mínima de una componente respecto a su fila. Por debajo es ruido:
# un punto de tinta, un trozo de cuadrícula, el borde del papel.
ALTURA_MINIMA = 0.25
AREA_MINIMA = 30
# Distancia máxima al centro de una columna, en anchuras de cifra, para
# aceptar que una componente del segundo sumando es una cifra y no el signo.
TOLERANCIA_COLUMNA = 0.7
# Largo mínimo de un trazo horizontal, en alturas de la fila, para tomarlo
# por la raya de la suma o una línea de la cuadrícula y no por parte de una
# cifra.
LARGO_RAYA = 1.2
# Fracción de la pieza más estrecha que tienen que solaparse en horizontal
# dos piezas de una fila para tomarlas por trozos de la misma cifra.
SOLAPE_MISMA_CIFRA = 0.5
# Distancia máxima entre dos centros, en alturas de cifra, para considerarlos
# la misma columna de la suma.
TOLERANCIA_AGRUPAR = 0.45
# Confianza mínima media para dar por buena la lectura de una fila.
CONFIANZA_MINIMA = float(os.environ.get('CONFIANZA_DIGITOS', '0.55'))


def ruta_modelo():
    return Path(os.environ.get('MODELO_DIGITOS', str(MODELO_POR_OMISION)))


def modelo_disponible():
    """¿Existe el archivo del clasificador?

    Se comprueba el archivo antes de importar torch: en un equipo sin el
    modelo no tiene sentido pagar el coste de cargar la biblioteca.
    """
    try:
        return ruta_modelo().is_file()
    except OSError:
        return False


def construir_red():
    """Red pequeña a propósito.

    Diez clases y un trazo centrado en 28x28 no necesitan más, y el conjunto
    de entrenamiento es de unos cientos de ejemplos: una red grande se
    aprendería las fotografías en vez de la forma de las cifras.
    """
    import torch.nn as nn

    return nn.Sequential(
        nn.Conv2d(1, 32, 3, padding=1), nn.BatchNorm2d(32), nn.ReLU(),
        nn.Conv2d(32, 32, 3, padding=1), nn.BatchNorm2d(32), nn.ReLU(),
        nn.MaxPool2d(2),
        nn.Conv2d(32, 64, 3, padding=1), nn.BatchNorm2d(64), nn.ReLU(),
        nn.Conv2d(64, 64, 3, padding=1), nn.BatchNorm2d(64), nn.ReLU(),
        nn.MaxPool2d(2),
        nn.Dropout(0.3),
        nn.Flatten(),
        nn.Linear(64 * 7 * 7, 128), nn.ReLU(), nn.Dropout(0.4),
        nn.Linear(128, 10),
    )


@lru_cache(maxsize=1)
def cargar_clasificador(ruta=None):
    import torch

    destino = Path(ruta) if ruta else ruta_modelo()
    datos = torch.load(destino, map_location='cpu', weights_only=False)
    red = construir_red()
    red.load_state_dict(datos['estado'])
    red.eval()
    return red


def sin_trazos_largos(binaria, alto):
    """Borrar de la fila los trazos horizontales más largos que una cifra.

    La raya de la suma suele tocar la parte de abajo del segundo sumando, y
    con ella las cifras y la raya forman una sola pieza ancha. Separarla
    después a base de cortes acaba partiendo por sitios que no son fronteras
    de cifra. Es mejor quitar la raya antes de etiquetar.

    Lo que distingue la raya de una cifra es la longitud: ningún trazo
    horizontal de una cifra (la barra del 7, el pie del 2, la del 4) es más
    largo que la propia altura de la cifra, y la raya de la suma lo es con
    mucho. Una apertura con un núcleo plano más largo que esa altura deja
    solo lo que es horizontal y largo; eso se resta y el resto queda intacto.
    También se lleva las líneas horizontales de la cuadrícula que hayan
    pasado el umbral.
    """
    import cv2

    # Longitud impar: con un núcleo par OpenCV desplaza el ancla un píxel y
    # la raya se resta con una columna de menos en un extremo.
    largo = max(15, int(round(alto * LARGO_RAYA))) | 1
    if largo >= binaria.shape[1]:
        return binaria
    nucleo = cv2.getStructuringElement(cv2.MORPH_RECT, (largo, 1))
    rayas = cv2.morphologyEx(binaria, cv2.MORPH_OPEN, nucleo)
    return cv2.subtract(binaria, rayas)


def componentes_de(gris, caja):
    """Componentes conexas dentro de una caja, en coordenadas de la imagen.

    Se devuelven ordenadas de izquierda a derecha, que es el orden en que se
    leen las cifras.
    """
    import cv2

    x1, y1, x2, y2 = (int(v) for v in caja)
    recorte = gris[y1:y2, x1:x2]
    if recorte.size == 0:
        return []
    _, binaria = cv2.threshold(recorte, 0, 255,
                               cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    alto, ancho = recorte.shape
    binaria = sin_trazos_largos(binaria, alto)
    cantidad, _, stats, _ = cv2.connectedComponentsWithStats(binaria, 8)
    cajas = []
    for indice in range(1, cantidad):
        x, y, w, h, area = stats[indice]
        if h < alto * ALTURA_MINIMA or area < AREA_MINIMA:
            continue
        # Ancha y plana: es la raya de la suma, no una cifra.
        if w > ancho * 0.6 and h < alto * ALTURA_MINIMA * 2:
            continue
        cajas.append((x1 + x, y1 + y, w, h))
    cajas.sort(key=lambda c: c[0])
    return cajas


def sin_signo_mas(cajas_b, referencias):
    """Quitar el signo + del segundo sumando usando las columnas.

    En una suma vertical las cifras se alinean en columnas; el signo queda
    fuera de todas ellas, a la izquierda. Comparar con las columnas de las
    otras dos filas resulta más fiable que medir el hueco entre trazos, que
    cambia con la letra de cada persona.

    Solo se descarta por la izquierda: una componente desalineada en medio de
    la fila es más probable que sea una cifra torcida que un signo.
    """
    import numpy as np

    if not cajas_b:
        return cajas_b
    centros = [c[0] + c[2] / 2 for fila in referencias for c in fila]
    if not centros:
        return cajas_b
    anchuras = [c[2] for fila in referencias for c in fila]
    anchura = float(np.median(anchuras)) if anchuras else 10.0
    if anchura <= 0:
        anchura = 10.0

    salida = list(cajas_b)
    while salida:
        centro = salida[0][0] + salida[0][2] / 2
        if min(abs(centro - c) for c in centros) <= anchura * TOLERANCIA_COLUMNA:
            break
        salida.pop(0)

    return salida


def normalizar(gris, caja):
    """Dejar una cifra centrada en un cuadrado de lado fijo.

    Se conserva la proporción: estirar un 1 hasta llenar el cuadro lo
    acercaría a un 8, y encoger un 8 lo acercaría a un 1.
    """
    import cv2
    import numpy as np

    x, y, w, h = caja
    recorte = gris[y:y + h, x:x + w]
    _, binaria = cv2.threshold(recorte, 0, 255,
                               cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    lado_util = LADO - 8
    escala = min(lado_util / max(w, 1), lado_util / max(h, 1))
    nuevo = (max(1, int(round(w * escala))), max(1, int(round(h * escala))))
    pequena = cv2.resize(binaria, nuevo, interpolation=cv2.INTER_AREA)
    lienzo = np.zeros((LADO, LADO), dtype=np.uint8)
    dx = (LADO - nuevo[0]) // 2
    dy = (LADO - nuevo[1]) // 2
    lienzo[dy:dy + nuevo[1], dx:dx + nuevo[0]] = pequena
    return lienzo


def columnas_comunes(por_fila):
    """Columnas de la suma, deducidas de las tres filas a la vez.

    Las cifras de una suma vertical quedan alineadas. Un centro que aparece
    en dos filas distintas marca una columna; uno que aparece en una sola
    puede ser cualquier cosa y no se tiene en cuenta.
    """
    import numpy as np

    cajas = [c for fila in por_fila.values() for c in fila]
    if len(cajas) < 2:
        return [], 0.0
    altura = float(np.median([c[3] for c in cajas]))
    if altura <= 0:
        return [], 0.0
    tolerancia = altura * TOLERANCIA_AGRUPAR
    centros = sorted(c[0] + c[2] / 2 for c in cajas)
    grupos = [[centros[0]]]
    for centro in centros[1:]:
        if centro - grupos[-1][-1] <= tolerancia:
            grupos[-1].append(centro)
        else:
            grupos.append([centro])
    return [float(np.mean(g)) for g in grupos if len(g) >= 2], altura


def reparar_fila(gris, cajas, columnas, altura):
    """Partir una pieza solo si la fila tiene menos cifras que columnas cubre.

    Esta condición es la que hace seguro el arreglo. De las filas de ensayo,
    383 se separan bien y 28 no; cualquier retoque que actúe sobre todas
    estropea más de las que salva. Aquí no se toca una fila cuyo número de
    piezas ya cuadre con las columnas que ocupa: se repara únicamente la que
    delata por sí misma que le falta una cifra, porque abarca más columnas
    que piezas tiene.

    Las columnas dicen dónde cae la frontera; el corte se afina luego al
    punto de menos tinta de su entorno, que es el cuello que dejan dos
    cifras al tocarse.
    """
    import cv2
    import numpy as np

    if not cajas or not columnas or altura <= 0:
        return cajas
    margen = altura * TOLERANCIA_AGRUPAR
    izquierda = min(c[0] for c in cajas) - margen
    derecha = max(c[0] + c[2] for c in cajas) + margen
    cubiertas = [c for c in columnas if izquierda <= c <= derecha]
    if len(cubiertas) <= len(cajas):
        return cajas

    salida = []
    for caja in cajas:
        x, y, w, h = caja[:4]
        dentro = [c for c in cubiertas if x < c < x + w]
        if len(dentro) < 2:
            salida.append(caja)
            continue
        recorte = gris[y:y + h, x:x + w]
        if recorte.size == 0:
            salida.append(caja)
            continue
        _, binaria = cv2.threshold(recorte, 0, 255,
                                   cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        perfil = binaria.sum(axis=0).astype(float)
        ventana = max(1, int(altura * .2))
        cortes = []
        for izq, der in zip(dentro, dentro[1:]):
            centro = int(round((izq + der) / 2 - x))
            desde = max(1, centro - ventana)
            hasta = min(w - 1, centro + ventana + 1)
            if desde < hasta:
                cortes.append(desde + int(np.argmin(perfil[desde:hasta])))
        cortes = sorted(set(c for c in cortes if 0 < c < w))
        if not cortes:
            salida.append(caja)
            continue
        bordes = [0] + cortes + [w]
        for izq, der in zip(bordes, bordes[1:]):
            if der > izq:
                salida.append((x + izq, y, der - izq, h))
    return salida


def unir_partidas(cajas, columnas, altura):
    """Unir piezas de sobra solo si la fila tiene más que columnas cubre.

    Es el caso contrario a reparar_fila: una cifra cuyo trazo se interrumpe
    deja dos piezas en la misma columna. Lleva la misma condición de
    seguridad, porque el riesgo es el mismo: una fila cuyo número de piezas
    ya cuadre con sus columnas no se toca.
    """
    if not cajas or not columnas or altura <= 0:
        return cajas
    margen = altura * TOLERANCIA_AGRUPAR
    izquierda = min(c[0] for c in cajas) - margen
    derecha = max(c[0] + c[2] for c in cajas) + margen
    cubiertas = [c for c in columnas if izquierda <= c <= derecha]
    if not cubiertas or len(cajas) <= len(cubiertas):
        return cajas

    grupos = {}
    for caja in cajas:
        centro = caja[0] + caja[2] / 2
        columna = min(range(len(cubiertas)),
                      key=lambda i: abs(centro - cubiertas[i]))
        grupos.setdefault(columna, []).append(caja)
    salida = []
    for columna in sorted(grupos):
        piezas = grupos[columna]
        x1 = min(c[0] for c in piezas)
        y1 = min(c[1] for c in piezas)
        x2 = max(c[0] + c[2] for c in piezas)
        y2 = max(c[1] + c[3] for c in piezas)
        salida.append((x1, y1, x2 - x1, y2 - y1))
    return salida


def unir_solapadas(cajas):
    """Unir piezas de una misma fila que están una encima de la otra.

    Dos cifras distintas de una fila nunca se solapan en horizontal: van una
    al lado de la otra. Cuando dos piezas sí lo hacen, son una sola cifra que
    se rompió al binarizar, como un 7 con raya cruzada cuya raya queda
    suelta del palo; sin unirlas, cada trozo se lee como un 1 y "37" sale
    "311". A diferencia de unir_partidas, esto no depende de las columnas, así
    que vale también para el resultado.
    """
    salida = []
    for caja in sorted(cajas, key=lambda c: c[0]):
        if salida:
            x, y, w, h = salida[-1][:4]
            cx, cy, cw, ch = caja[:4]
            solape = min(x + w, cx + cw) - max(x, cx)
            if solape > SOLAPE_MISMA_CIFRA * min(w, cw):
                x1, y1 = min(x, cx), min(y, cy)
                x2, y2 = max(x + w, cx + cw), max(y + h, cy + ch)
                salida[-1] = (x1, y1, x2 - x1, y2 - y1)
                continue
        salida.append(caja)
    return salida


def separar_cifras(gris, cajas_de_fila, nombres):
    """Separar las tres filas en cifras sueltas, ya sin el signo +."""
    por_fila = {n: unir_solapadas(componentes_de(gris, cajas_de_fila[n]))
                for n in nombres}
    referencia = [por_fila[n] for n in nombres if n != 'operando_b']
    if 'operando_b' in por_fila:
        por_fila['operando_b'] = sin_signo_mas(por_fila['operando_b'], referencia)
    columnas, altura = columnas_comunes(por_fila)
    por_fila = {n: reparar_fila(gris, c, columnas, altura)
                for n, c in por_fila.items()}
    # La unión no se aplica al resultado. Su cifra de acarreo ocupa una
    # columna que no existe en ninguna otra fila, así que no se detecta como
    # columna y la cifra acabaría fundida con la de al lado: medido, el
    # resultado pasaba de 130 filas correctas a 121.
    por_fila = {n: (unir_partidas(c, columnas, altura)
                    if n != 'resultado' else c)
                for n, c in por_fila.items()}
    return por_fila


def _recortar_resultado(por_fila, nombres):
    """Descartar por la izquierda las piezas que el resultado no puede tener.

    Al sumar dos números el acarreo que sale nunca pasa de uno, así que el
    resultado tiene como mucho una cifra más que el operando más largo. Si la
    separación encontró más piezas que eso, las de la izquierda no son cifras:
    suelen ser un trazo de la cuadrícula o un resto de la raya, que el
    clasificador transcribe como un "1".

    Es una comprobación de geometría, no de aritmética: cuenta piezas, no mira
    qué cifra es cada una, y nunca se apoya en el resultado correcto de la
    suma. Un niño que se equivoca sigue leyéndose tal como escribió, que es
    justamente lo que el tutor necesita ver.
    """
    if len(nombres) < 3:
        return
    a, b, resultado = nombres[0], nombres[1], nombres[2]
    if not por_fila.get(a) or not por_fila.get(b):
        return
    maximo = max(len(por_fila[a]), len(por_fila[b])) + 1
    sobran = len(por_fila[resultado]) - maximo
    if sobran > 0:
        por_fila[resultado] = por_fila[resultado][sobran:]


def imagen_de_tinta(imagen):
    """Imagen en la que solo la tinta azul es oscura.

    Hasta ahora las cifras se separaban binarizando la luminancia, y en la
    luminancia la sombra de una hoja y las líneas de la cuadrícula se parecen
    a la tinta: en las capturas de cámara, la sombra entre "1", "0" y "4"
    contaba como trazo y las tres cifras salían como una sola pieza.

    Lo que distingue la tinta es el color. Una sombra o una línea gris tienen
    el rojo, el verde y el azul parecidos; la tinta azul tiene mucho más azul
    que lo demás. Se toma, por eso, cuánto supera el azul al mayor de los
    otros dos canales, y se invierte para que la tinta quede oscura sobre
    fondo claro, como espera el resto del código. El aplicativo ya exige
    bolígrafo azul para encontrar las filas, así que esto no añade ninguna
    condición nueva.

    La usa tanto la lectura como la extracción de cifras para entrenar, para
    que la red aprenda con los mismos recortes que luego va a ver.
    """
    import numpy as np

    rgb = np.asarray(imagen.convert('RGB')).astype(np.int16)
    azul = rgb[:, :, 2] - np.maximum(rgb[:, :, 0], rgb[:, :, 1])
    azul = np.clip(azul, 0, None).astype(np.float32)
    techo = float(np.percentile(azul, 99.5)) if azul.size else 0.0
    if techo <= 0:
        return np.asarray(imagen.convert('L'))
    escalada = np.clip(azul * (255.0 / techo), 0, 255)
    return (255 - escalada).astype(np.uint8)


def _leer_vista(red, gris, cajas_de_fila, nombres):
    """Leer las tres filas sobre una de las dos imágenes de la fotografía.

    Devuelve, por fila, el texto propuesto, la confianza media y la de la
    cifra más dudosa.
    """
    import numpy as np
    import torch

    por_fila = separar_cifras(gris, cajas_de_fila, nombres)
    _recortar_resultado(por_fila, nombres)
    lecturas = {}
    for nombre in nombres:
        cifras = por_fila[nombre]
        if not cifras:
            lecturas[nombre] = ('', 0.0, 0.0)
            continue
        lote = np.stack([normalizar(gris, c) for c in cifras])
        tensor = torch.from_numpy(lote.astype(np.float32) / 255.0).unsqueeze(1)
        with torch.inference_mode():
            salida = torch.softmax(red(tensor), dim=1)
        probabilidad, clase = salida.max(dim=1)
        texto = ''.join(str(int(c)) for c in clase)
        lecturas[nombre] = (texto, float(probabilidad.mean()),
                            float(probabilidad.min()))
    return lecturas


def vistas_de(imagen):
    """Las dos imágenes sobre las que se lee: la de tinta azul y la de brillo.

    Cada una acierta donde la otra falla. La de tinta borra sombras y
    cuadrícula y es mejor con las fotografías de un móvil; la de brillo
    aguanta mejor el color pobre de la cámara de un portátil. Medido con tres
    entrenamientos distintos: con la de tinta, 47 de 50 en RNF-02 y entre 6 y
    8 de 19 capturas de portátil; con la de brillo, 42 de 50 y entre 8 y 9.
    """
    import numpy as np

    return [imagen_de_tinta(imagen), np.asarray(imagen.convert('L'))]


def leer_filas(imagen, cajas_de_fila, nombres, ruta=None):
    """Transcribir las tres filas clasificando cada cifra por separado.

    Se lee la fotografía sobre las dos imágenes de vistas_de y, fila a fila,
    se queda la lectura en la que la red está más segura de su cifra más
    dudosa. Mirar la cifra más dudosa y no la media evita preferir una fila
    con tres cifras claras y una inventada.

    Devuelve un diccionario de textos y otro de confianzas medias por fila.
    Una fila cuya confianza media no llegue al mínimo se devuelve vacía: es
    preferible que el estudiante complete el campo en la pantalla de
    confirmación a que el sistema proponga una cifra inventada.
    """
    red = cargar_clasificador(ruta)
    por_vista = [_leer_vista(red, gris, cajas_de_fila, nombres)
                 for gris in vistas_de(imagen)]

    textos, confianzas = {}, {}
    for nombre in nombres:
        texto, media, _ = max((v[nombre] for v in por_vista),
                              key=lambda lectura: lectura[2])
        confianzas[nombre] = media
        textos[nombre] = texto if texto and media >= CONFIANZA_MINIMA else ''
    return textos, confianzas