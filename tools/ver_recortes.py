"""Guardar los recortes tal como los recibe el lector, para mirarlos.

Todo el diagnóstico hecho hasta ahora es indirecto: se deduce qué pasa a
partir de lo que el modelo transcribe. Mirar la imagen que el modelo recibe
cierra esa brecha, y es barato.

Guarda, por cada fotografía, los tres recortes ya preparados —enderezados,
con el contraste normalizado y el borde blanco— con el nombre del campo y lo
que el lector transcribió, de modo que al verlos se entienda de dónde sale
cada cifra de sobra.

Uso:
    python tools/ver_recortes.py local_ocr/evaluacion_ocr --solo e04 e08 e36
    python tools/ver_recortes.py local_ocr/evaluacion_ocr --fallos
"""
import argparse
import csv
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

CAMPOS = ('operand_a', 'operand_b', 'written_result')
# Los recortes se guardan con nombres en castellano y los campos de la lectura
# en inglés. Esta correspondencia evita confundir unos con otros.
RECORTE_DE = {
    'operand_a': 'operando_a',
    'operand_b': 'operando_b',
    'written_result': 'resultado',
}
FORMATOS = {'.jpg', '.jpeg', '.png'}


def referencia_de(carpeta):
    ruta = carpeta / 'referencia_ocr.csv'
    if not ruta.is_file():
        return {}
    with ruta.open(encoding='utf-8-sig', newline='') as archivo:
        primera = archivo.readline()
        archivo.seek(0)
        lector = csv.DictReader(archivo, delimiter=';' if ';' in primera else ',')
        return {
            fila['archivo'].strip(): {
                campo: (fila.get(campo) or '').strip() for campo in CAMPOS
            }
            for fila in lector if (fila.get('archivo') or '').strip()
        }


def solo_digitos(valor):
    return ''.join(ch for ch in str(valor if valor is not None else '') if ch.isdigit())


def main():
    analizador = argparse.ArgumentParser(description=__doc__)
    analizador.add_argument('carpeta', type=Path)
    analizador.add_argument('--salida', type=Path, default=None,
                            help='Dónde dejar los recortes. Por omisión, '
                                 'una subcarpeta "recortes".')
    analizador.add_argument('--solo', nargs='*', default=None,
                            help='Nombres o prefijos de fotografías concretas.')
    analizador.add_argument('--fallos', action='store_true',
                            help='Solo las fotografías con algún campo mal.')
    argumentos = analizador.parse_args()

    from tutoring.services import handwriting as hw

    esperado = referencia_de(argumentos.carpeta)
    fotos = sorted(p for p in argumentos.carpeta.iterdir()
                   if p.suffix.lower() in FORMATOS)
    if argumentos.solo:
        claves = tuple(argumentos.solo)
        fotos = [p for p in fotos if p.stem.startswith(claves) or p.name in claves]
    if not fotos:
        raise SystemExit('No hay fotografías que encajen.')

    destino = argumentos.salida or (argumentos.carpeta / 'recortes')
    destino.mkdir(parents=True, exist_ok=True)

    print(f'Modelo: {hw.MODELO}')
    print('Cargando...', flush=True)
    hw.cargar_modelo(hw.MODELO, True)

    guardadas = 0
    for foto in fotos:
        try:
            _, _, recortes, _, _ = hw.preparar_suma(foto)
        except Exception as exc:  # noqa: BLE001
            print(f'  {foto.name}: no se pudo separar ({exc})')
            continue

        try:
            lectura = hw.leer_fotografia(foto, incluir_diagnostico=True)
        except Exception as exc:  # noqa: BLE001
            print(f'  {foto.name}: no se pudo leer ({exc})')
            continue

        crudas = lectura.get('lecturas_crudas') or {}
        propuesta = lectura.get('propuesta') or {}
        referencia = esperado.get(foto.name, {})

        hay_fallo = any(
            solo_digitos(propuesta.get(c)) != solo_digitos(referencia.get(c, ''))
            for c in CAMPOS
        ) if referencia else True
        if argumentos.fallos and not hay_fallo:
            continue

        for campo in CAMPOS:
            crudo = solo_digitos(crudas.get(campo, '')) or 'nada'
            correcto = solo_digitos(referencia.get(campo, '')) or '?'
            # El nombre lleva lo esperado y lo leído: así la carpeta se puede
            # ojear sin tener el informe al lado.
            nombre = f'{foto.stem}__{campo}__esperado-{correcto}__leyo-{crudo}.png'
            recortes[RECORTE_DE[campo]].save(destino / nombre)
            guardadas += 1

        marca = 'fallo' if hay_fallo else 'bien '
        print(f'  {marca} {foto.name}', flush=True)

    print()
    print(f'Guardados {guardadas} recortes en: {destino}')
    print()
    print('Qué mirar en ellos:')
    print('  - ¿Se ven las rayas del cuaderno cuadriculado dentro del recorte?')
    print('    Una raya vertical se transcribe como un 1.')
    print('  - ¿Entra el signo + en el recorte del segundo sumando?')
    print('  - ¿Entra la raya de la suma por abajo?')
    print('  - ¿Asoma alguna cifra de la fila de arriba o de abajo?')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())