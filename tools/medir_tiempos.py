"""Medir en qué etapa se va el tiempo de una lectura.

Antes de optimizar hay que saber qué tarda. Este guion separa las tres
etapas con una fotografía real y las cronometra por separado:

1. Carga del modelo (solo la primera vez por proceso).
2. Separación de las tres filas (OpenCV, con rescate YOLO si hace falta).
3. Reconocimiento de las cifras (TrOCR).

Además compara el reconocimiento con búsqueda por haces (num_beams=3, el
ajuste actual) y sin ella (num_beams=1), que es la palanca de velocidad más
grande que queda. La comparación es solo de tiempo: decidir cambiarlo exige
repetir el ensayo de exactitud sobre las 50 fotografías.

Uso:
    python tools/medir_tiempos.py ruta/a/una/foto.jpg
    python tools/medir_tiempos.py carpeta_con_fotos/ --repeticiones 3
"""
import argparse
import statistics
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

EXTENSIONES = {'.jpg', '.jpeg', '.png'}


def cronometrar(funcion, *args, **kwargs):
    inicio = time.perf_counter()
    resultado = funcion(*args, **kwargs)
    return resultado, time.perf_counter() - inicio


def fotografias(destino):
    ruta = Path(destino)
    if ruta.is_file():
        return [ruta]
    return sorted(hijo for hijo in ruta.iterdir()
                  if hijo.suffix.lower() in EXTENSIONES)


def reconocer(recortes, haces):
    """Reconocer los tres recortes con el número de haces indicado."""
    import torch

    from tutoring.services.handwriting import RECORTES, cargar_modelo

    procesador, reconocedor = cargar_modelo()
    valores = procesador(images=[recortes[nombre] for nombre in RECORTES],
                         return_tensors='pt').pixel_values
    with torch.inference_mode():
        ids = reconocedor.generate(valores, max_new_tokens=12, num_beams=haces)
    return procesador.batch_decode(ids, skip_special_tokens=True)


def main():
    analizador = argparse.ArgumentParser(description=__doc__)
    analizador.add_argument('destino', help='Fotografía o carpeta de fotografías.')
    analizador.add_argument('--repeticiones', type=int, default=1,
                            help='Veces que se repite cada reconocimiento.')
    argumentos = analizador.parse_args()

    from tutoring.services.handwriting import (
        PhotoNotReadable, cargar_modelo, preparar_suma,
    )

    archivos = fotografias(argumentos.destino)
    if not archivos:
        print('No se encontraron fotografías.')
        return 1

    print('Cargando el modelo de lectura...')
    _, carga = cronometrar(cargar_modelo)
    print(f'  Carga del modelo: {carga:.2f} s')
    print('  (solo ocurre una vez por proceso; en el servidor, en la primera')
    print('   lectura tras cada reinicio)\n')

    separaciones = []
    con_haces = []
    sin_haces = []

    for archivo in archivos:
        print(f'{archivo.name}')
        # preparar_suma acepta la ruta y se encarga de abrir y validar la
        # fotografía igual que lo hace el aplicativo, de modo que lo medido
        # aquí es el mismo trabajo que ocurre en una lectura real.
        try:
            salida, duracion = cronometrar(preparar_suma, archivo)
        except PhotoNotReadable as exc:
            print(f'  separación fallida: {exc}\n')
            continue
        except Exception as exc:  # noqa: BLE001
            print(f'  separación fallida: {exc}\n')
            continue

        # preparar_suma devuelve (imagen, vista, recortes, cajas, ángulo).
        # Los recortes son las imágenes que recibe el lector; las cajas son
        # coordenadas y no sirven aquí.
        _, _, recortes, _, _ = salida
        separaciones.append(duracion)
        print(f'  Separación: {duracion:.2f} s')

        for haces, acumulador in ((3, con_haces), (1, sin_haces)):
            medidas = []
            for _ in range(argumentos.repeticiones):
                texto, duracion = cronometrar(reconocer, recortes, haces)
                medidas.append(duracion)
            media = statistics.mean(medidas)
            acumulador.append(media)
            etiqueta = 'con haces (actual)' if haces == 3 else 'sin haces      '
            print(f'  Reconocimiento {etiqueta}: {media:.2f} s  ->  {texto}')
        print()

    if not separaciones:
        print('Ninguna fotografía llegó a medirse.')
        return 1

    print('=' * 58)
    print(f'Fotografías medidas: {len(separaciones)}')
    print(f'Separación      media {statistics.mean(separaciones):.2f} s  '
          f'máximo {max(separaciones):.2f} s')
    print(f'Lectura actual  media {statistics.mean(con_haces):.2f} s  '
          f'máximo {max(con_haces):.2f} s')
    print(f'Lectura sin haces media {statistics.mean(sin_haces):.2f} s  '
          f'máximo {max(sin_haces):.2f} s')
    ahorro = statistics.mean(con_haces) - statistics.mean(sin_haces)
    print(f'Ahorro por quitar los haces: {ahorro:.2f} s por fotografía')
    print()
    print('El total por lectura es separación + reconocimiento, sin contar la')
    print('carga del modelo. Compáralo con RNF-01 (10 s).')
    print('Quitar los haces NO es gratis: cambia lo que el modelo transcribe.')
    print('Antes de adoptarlo hay que repetir el ensayo de exactitud sobre las')
    print('50 fotografías y comprobar que 24/50 no empeora.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())