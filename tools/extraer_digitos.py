"""Extraer cifras sueltas y etiquetarlas solas, a partir de las referencias.

El lector actual transcribe una fila entera como si fuera texto libre, y por
eso puede inventarse caracteres: medido sobre las 50 fotografías del ensayo,
veinte lecturas se descartaron porque traían un dígito de más, casi siempre
un "1" salido de un trazo vertical cualquiera.

Un clasificador de cifras no puede hacer eso: recibe el recorte de UNA cifra
y devuelve una clase del 0 al 9. El modo de fallo desaparece por construcción.
Pero para entrenarlo hacen falta cifras recortadas y etiquetadas, y aquí es
donde el proyecto tiene una ventaja: ya existe la referencia con lo que hay
escrito en cada fotografía.

Si una fila que la referencia dice que es "123" se separa en exactamente tres
componentes, entonces de izquierda a derecha son el 1, el 2 y el 3. La
etiqueta sale gratis, sin que nadie marque nada a mano.

Cuando el número de componentes NO coincide con el de la referencia, la fila
se descarta: etiquetar a ciegas ahí metería ejemplos equivocados en el
entrenamiento, que es peor que no tenerlos. Medido sobre 21 fotografías en
hoja lisa, coinciden 60 de 63 filas.

Uso:
    python tools/extraer_digitos.py local_ocr/prueba_a4
    python tools/extraer_digitos.py local_ocr/evaluacion_ocr --salida local_ocr/digitos
"""
import argparse
import csv
import sys
from collections import Counter
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

CAMPO_DE = {
    'operando_a': 'operand_a',
    'operando_b': 'operand_b',
    'resultado': 'written_result',
}
FORMATOS = {'.jpg', '.jpeg', '.png'}


def referencia_de(carpeta):
    ruta = carpeta / 'referencia_ocr.csv'
    if not ruta.is_file():
        raise SystemExit(f'No se encuentra {ruta}')
    with ruta.open(encoding='utf-8-sig', newline='') as archivo:
        primera = archivo.readline()
        archivo.seek(0)
        lector = csv.DictReader(archivo, delimiter=';' if ';' in primera else ',')
        return {
            fila['archivo'].strip(): fila
            for fila in lector if (fila.get('archivo') or '').strip()
        }


def solo_digitos(valor):
    return ''.join(c for c in str(valor or '') if c.isdigit())


def main():
    analizador = argparse.ArgumentParser(description=__doc__)
    analizador.add_argument('carpeta', type=Path)
    analizador.add_argument('--salida', type=Path, default=None,
                            help='Dónde dejar las cifras. Por omisión, '
                                 'local_ocr/digitos.')
    argumentos = analizador.parse_args()

    from PIL import Image

    from tutoring.services.digitos import normalizar, separar_cifras, vistas_de
    from tutoring.services.handwriting import RECORTES, preparar_suma

    esperado = referencia_de(argumentos.carpeta)
    fotos = sorted(p for p in argumentos.carpeta.iterdir()
                   if p.suffix.lower() in FORMATOS and p.name in esperado)
    if not fotos:
        raise SystemExit('No hay fotografías con referencia en esa carpeta.')

    destino = argumentos.salida or (RAIZ / 'local_ocr' / 'digitos')
    for clase in range(10):
        (destino / str(clase)).mkdir(parents=True, exist_ok=True)

    cuenta = Counter()
    filas_usadas = 0
    filas_descartadas = 0
    fotos_fallidas = 0

    for indice, foto in enumerate(fotos, 1):
        try:
            imagen, _, _, cajas, _ = preparar_suma(foto)
        except Exception as exc:  # noqa: BLE001
            fotos_fallidas += 1
            print(f'  {foto.name}: no se pudo separar ({exc})')
            continue

        # Se extrae de las dos imágenes sobre las que lee el aplicativo, la
        # de tinta y la de brillo, para que la red aprenda las dos.
        for vista, gris in enumerate(vistas_de(imagen)):
            por_fila = separar_cifras(gris, cajas, RECORTES)

            for nombre in RECORTES:
                etiquetas = solo_digitos(esperado[foto.name][CAMPO_DE[nombre]])
                encontradas = por_fila[nombre]
                if not etiquetas or len(encontradas) != len(etiquetas):
                    filas_descartadas += 1
                    continue
                for posicion, (caja, digito) in enumerate(zip(encontradas, etiquetas)):
                    imagen_digito = Image.fromarray(normalizar(gris, caja))
                    nombre_archivo = f'{foto.stem}_{nombre}_{posicion}_v{vista}.png'
                    imagen_digito.save(destino / digito / nombre_archivo)
                    cuenta[digito] += 1
                filas_usadas += 1

        print(f'  {indice}/{len(fotos)} {foto.name}', flush=True)

    print()
    print('=' * 56)
    print(f'Filas aprovechadas: {filas_usadas}')
    print(f'Filas descartadas (no cuadraba el número de cifras): '
          f'{filas_descartadas}')
    if fotos_fallidas:
        print(f'Fotografías sin separar: {fotos_fallidas}')
    print(f'Cifras extraídas: {sum(cuenta.values())}')
    print()
    print('Por clase:')
    for clase in '0123456789':
        print(f'  {clase}: {cuenta[clase]}')
    print()
    print(f'Guardadas en: {destino}')
    print()
    faltan = [c for c in '0123456789' if cuenta[c] < 10]
    if faltan:
        print('Clases con menos de 10 ejemplos: ' + ', '.join(faltan))
        print('Conviene añadir fotografías que las contengan antes de entrenar.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
