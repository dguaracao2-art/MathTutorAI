"""Entrenar un clasificador de cifras con las imágenes ya extraídas.

Es una red pequeña y a propósito: el problema no es difícil —diez clases, un
trazo centrado en 28x28— y el conjunto de entrenamiento es de unos cientos de
ejemplos, así que una red grande se aprendería las fotografías de memoria en
lugar de la forma de las cifras.

La ventaja frente al lector de texto actual es estructural, no de tamaño:
este modelo recibe UNA cifra y devuelve una clase del 0 al 9. No puede
insertar un dígito de más, que es el fallo que se midió veinte veces sobre
las 50 fotografías del ensayo.

El aumento de datos (giros y desplazamientos pequeños) es lo que permite
entrenar con pocos ejemplos sin memorizarlos. Los giros se mantienen suaves:
un 6 girado de más se convierte en un 9.

Uso:
    python tools/entrenar_digitos.py local_ocr/digitos
    python tools/entrenar_digitos.py local_ocr/digitos --epocas 60
"""
import argparse
import random
import sys
from collections import Counter
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

LADO = 28
SEMILLA = 7


def cargar(carpeta):
    """Leer las imágenes organizadas en subcarpetas 0..9."""
    import numpy as np
    from PIL import Image

    imagenes, etiquetas = [], []
    for clase in range(10):
        for archivo in sorted((carpeta / str(clase)).glob('*.png')):
            with Image.open(archivo) as imagen:
                matriz = np.asarray(imagen.convert('L'), dtype=np.float32)
            if matriz.shape != (LADO, LADO):
                continue
            imagenes.append(matriz / 255.0)
            etiquetas.append(clase)
    if not imagenes:
        raise SystemExit(f'No se encontraron imágenes en {carpeta}')
    return np.stack(imagenes), np.array(etiquetas)


def partir(imagenes, etiquetas, proporcion=0.2):
    """Separar validación manteniendo la proporción de cada clase.

    Con pocos ejemplos, una partición al azar puede dejar una clase entera
    fuera de la validación y dar un número que no significa nada.
    """
    import numpy as np

    generador = np.random.default_rng(SEMILLA)
    indices_val = []
    for clase in range(10):
        de_la_clase = np.flatnonzero(etiquetas == clase)
        generador.shuffle(de_la_clase)
        cuantos = max(1, int(round(len(de_la_clase) * proporcion)))
        indices_val.extend(de_la_clase[:cuantos].tolist())
    mascara = np.zeros(len(etiquetas), dtype=bool)
    mascara[indices_val] = True
    return (imagenes[~mascara], etiquetas[~mascara],
            imagenes[mascara], etiquetas[mascara])


def aumentar(lote):
    """Giros, desplazamientos y escalas pequeños sobre un lote."""
    import numpy as np
    import torch
    import torch.nn.functional as F

    n = lote.shape[0]
    angulo = torch.empty(n).uniform_(-0.17, 0.17)      # ±10 grados
    escala = torch.empty(n).uniform_(0.88, 1.12)
    mover_x = torch.empty(n).uniform_(-0.12, 0.12)
    mover_y = torch.empty(n).uniform_(-0.12, 0.12)
    coseno = torch.cos(angulo) / escala
    seno = torch.sin(angulo) / escala
    matriz = torch.zeros(n, 2, 3)
    matriz[:, 0, 0] = coseno
    matriz[:, 0, 1] = -seno
    matriz[:, 1, 0] = seno
    matriz[:, 1, 1] = coseno
    matriz[:, 0, 2] = mover_x
    matriz[:, 1, 2] = mover_y
    rejilla = F.affine_grid(matriz, lote.shape, align_corners=False)
    return F.grid_sample(lote, rejilla, align_corners=False,
                         padding_mode='zeros')


def main():
    analizador = argparse.ArgumentParser(description=__doc__)
    analizador.add_argument('carpeta', type=Path)
    analizador.add_argument('--epocas', type=int, default=80)
    analizador.add_argument('--lote', type=int, default=32)
    analizador.add_argument('--salida', type=Path,
                            default=RAIZ / 'local_yolo' / 'clasificador_digitos.pt')
    argumentos = analizador.parse_args()

    import numpy as np
    import torch
    import torch.nn as nn

    from tutoring.services.digitos import construir_red

    torch.manual_seed(SEMILLA)
    random.seed(SEMILLA)
    np.random.seed(SEMILLA)
    torch.set_num_threads(min(4, (__import__('os').cpu_count() or 2)))

    imagenes, etiquetas = cargar(argumentos.carpeta)
    print(f'Cifras cargadas: {len(etiquetas)}')
    reparto = Counter(etiquetas.tolist())
    print('Por clase: ' + '  '.join(f'{c}:{reparto[c]}' for c in range(10)))

    x_ent, y_ent, x_val, y_val = partir(imagenes, etiquetas)
    print(f'Entrenamiento: {len(y_ent)}   Validación: {len(y_val)}')
    print()

    x_ent = torch.from_numpy(x_ent).unsqueeze(1)
    y_ent = torch.from_numpy(y_ent).long()
    x_val = torch.from_numpy(x_val).unsqueeze(1)
    y_val = torch.from_numpy(y_val).long()

    red = construir_red()
    optimizador = torch.optim.AdamW(red.parameters(), lr=2e-3, weight_decay=1e-4)
    planificador = torch.optim.lr_scheduler.CosineAnnealingLR(
        optimizador, T_max=argumentos.epocas)
    perdida_fn = nn.CrossEntropyLoss(label_smoothing=0.05)

    mejor = 0.0
    mejor_estado = None
    for epoca in range(1, argumentos.epocas + 1):
        red.train()
        orden = torch.randperm(len(y_ent))
        total_perdida = 0.0
        for inicio in range(0, len(orden), argumentos.lote):
            indices = orden[inicio:inicio + argumentos.lote]
            lote = aumentar(x_ent[indices])
            optimizador.zero_grad()
            salida = red(lote)
            perdida = perdida_fn(salida, y_ent[indices])
            perdida.backward()
            optimizador.step()
            total_perdida += float(perdida) * len(indices)
        planificador.step()

        red.eval()
        with torch.inference_mode():
            aciertos = int((red(x_val).argmax(1) == y_val).sum())
        exactitud = aciertos / len(y_val)
        if exactitud >= mejor:
            mejor = exactitud
            mejor_estado = {k: v.clone() for k, v in red.state_dict().items()}
        if epoca % 10 == 0 or epoca == 1:
            print(f'  época {epoca:3d}   pérdida {total_perdida/len(y_ent):.3f}'
                  f'   validación {aciertos}/{len(y_val)} ({100*exactitud:.1f} %)')

    print()
    print(f'Mejor validación: {100*mejor:.1f} %')

    red.load_state_dict(mejor_estado)
    red.eval()
    with torch.inference_mode():
        predicho = red(x_val).argmax(1)
    confusiones = [(int(v), int(p)) for v, p in zip(y_val, predicho) if v != p]
    if confusiones:
        print('Confusiones en validación (esperado -> predicho):')
        for esperado, obtenido in Counter(confusiones).most_common():
            print(f'  {esperado[0]} -> {esperado[1]}   x{obtenido}')

    argumentos.salida.parent.mkdir(parents=True, exist_ok=True)
    torch.save({'estado': mejor_estado, 'lado': LADO,
                'validacion': mejor, 'ejemplos': int(len(etiquetas))},
               argumentos.salida)
    print()
    print(f'Modelo guardado en: {argumentos.salida}')
    print()
    print('La validación son pocos ejemplos y no sustituye a medir el sistema')
    print('completo sobre las fotografías con tools/medir_exactitud.py.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
