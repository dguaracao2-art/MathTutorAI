"""Comparar OCR con una referencia humana, antes de editar los números."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import re
import sys
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
CAMPOS = ('operand_a', 'operand_b', 'written_result')
CABECERA = ('archivo', *CAMPOS)
FORMATOS = {'.jpg', '.jpeg', '.png'}


def fotos_en(carpeta):
    return sorted(p for p in carpeta.iterdir() if p.is_file() and p.suffix.lower() in FORMATOS)


def crear_plantilla(carpeta):
    fotos = fotos_en(carpeta)
    if not fotos:
        raise ValueError('Primero coloca las fotografías JPG o PNG en esa carpeta.')
    salida = carpeta / 'referencia_ocr.csv'
    # No sobrescribir una transcripción que alguien ya haya revisado.
    with salida.open('x', newline='', encoding='utf-8-sig') as archivo:
        writer = csv.writer(archivo)
        writer.writerow(CABECERA)
        writer.writerows((p.name, '', '', '') for p in fotos)
    return salida


def con_llevadas(a, b):
    return any(int(x) + int(y) >= 10 for x, y in zip(str(a).zfill(3), str(b).zfill(3)))


def huella(ruta):
    if ruta.stat().st_size > 5 * 1024 * 1024:
        raise ValueError(f'{ruta.name}: supera los 5 MB.')
    return hashlib.sha256(ruta.read_bytes()).hexdigest()


def cargar_referencias(carpeta, *, final=False, ajuste=None):
    carpeta = carpeta.resolve()
    referencia = carpeta / 'referencia_ocr.csv'
    filas, nombres, huellas = [], set(), set()
    with referencia.open(newline='', encoding='utf-8-sig') as archivo:
        primera = archivo.readline()
        archivo.seek(0)
        reader = csv.DictReader(archivo, delimiter=';' if ';' in primera else ',')
        if len(reader.fieldnames or []) != 4 or set(reader.fieldnames or []) != set(CABECERA):
            raise ValueError('La referencia necesita las columnas: ' + ','.join(CABECERA))
        for numero, row in enumerate(reader, 2):
            if None in row or any(v is None for v in row.values()):
                raise ValueError(f'Fila {numero}: cantidad de columnas incorrecta.')
            nombre = row['archivo'].strip()
            if not nombre or '/' in nombre or '\\' in nombre:
                raise ValueError(f'Fila {numero}: utiliza solo el nombre de un archivo.')
            ruta = carpeta / nombre
            if ruta.suffix.lower() not in FORMATOS or not ruta.is_file() or ruta.resolve().parent != carpeta:
                raise ValueError(f'Fila {numero}: no se encuentra una foto admitida: {nombre}')
            if nombre.casefold() in nombres:
                raise ValueError(f'Archivo repetido: {nombre}')
            valores = {}
            for campo in CAMPOS:
                texto = row[campo].strip()
                limite = 9999 if campo == 'written_result' else 999
                if not re.fullmatch(r'[0-9]{1,4}', texto) or int(texto) > limite:
                    raise ValueError(f'Fila {numero}: completa {campo} con un entero entre 0 y {limite}.')
                valores[campo] = int(texto)
            digest = huella(ruta)
            if digest in huellas:
                raise ValueError(f'Foto duplicada, aunque tenga otro nombre: {nombre}')
            nombres.add(nombre.casefold())
            huellas.add(digest)
            filas.append({'archivo': nombre, **valores,
                          'con_llevadas': con_llevadas(valores['operand_a'], valores['operand_b'])})
    if not filas:
        raise ValueError('La referencia no contiene fotografías.')
    if final:
        if len(filas) != 50 or sum(f['con_llevadas'] for f in filas) != 25:
            raise ValueError('La evaluación final requiere 50 fotos: 25 sin llevadas y 25 con llevadas.')
        if {p.name.casefold() for p in fotos_en(carpeta)} != nombres:
            raise ValueError('En la carpeta final debe haber exactamente las 50 fotos de la referencia.')
        if ajuste is None or not ajuste.is_dir():
            raise ValueError('No se encuentra la carpeta de fotos usadas para ajustar el lector.')
        usadas = {huella(p) for p in fotos_en(ajuste)}
        if not usadas:
            raise ValueError('La carpeta de ajuste está vacía; conserva allí las fotos anteriores.')
        if huellas & usadas:
            raise ValueError('Hay fotos ya utilizadas para ajustar el lector. Usa fotos nuevas para la evaluación final.')
    return filas


def comparar(referencias, propuestas, *, final=False):
    if len(referencias) != len(propuestas) or not referencias:
        raise ValueError('Debe existir una propuesta por cada fotografía de referencia.')
    if final and (len(referencias) != 50 or sum(r['con_llevadas'] for r in referencias) != 25):
        raise ValueError('El resumen final requiere 50 referencias equilibradas.')
    detalles = []
    for ref, propuesta in zip(referencias, propuestas):
        aciertos = {c: type(propuesta.get(c)) is int and propuesta.get(c) == ref[c] for c in CAMPOS}
        detalles.append({'archivo': ref['archivo'], 'con_llevadas': ref['con_llevadas'],
                         **{f'referencia_{c}': ref[c] for c in CAMPOS},
                         **{f'lectura_{c}': propuesta.get(c) for c in CAMPOS},
                         **{f'acierto_{c}': aciertos[c] for c in CAMPOS},
                         'exacta': all(aciertos.values())})
    exactas = sum(d['exacta'] for d in detalles)
    resumen = {'modo': 'evaluacion_50' if final else 'ensayo', 'imagenes': len(detalles),
               'exactas': exactas, 'porcentaje_exacto': round(100 * exactas / len(detalles), 2),
               'aciertos_por_campo': {c: sum(d[f'acierto_{c}'] for d in detalles) for c in CAMPOS},
               'umbral_numerico_45_de_50': exactas >= 45 if final else None}
    for tipo, valor in (('sin_llevadas', False), ('con_llevadas', True)):
        grupo = [d for d in detalles if d['con_llevadas'] == valor]
        resumen[tipo] = {'imagenes': len(grupo), 'exactas': sum(d['exacta'] for d in grupo)}
    return detalles, resumen


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('carpeta', type=Path, help='Carpeta privada dentro de local_ocr/')
    parser.add_argument('--plantilla', action='store_true', help='Crear referencia_ocr.csv sin ejecutar OCR')
    parser.add_argument('--final', action='store_true', help='Exigir el conjunto de 50 fotos y comprobar duplicados')
    parser.add_argument('--ajuste', type=Path, default=ROOT / 'local_ocr' / 'pruebas')
    parser.add_argument('--salida', type=Path, help='Carpeta para guardar este ensayo por separado')
    args = parser.parse_args(argv)
    try:
        if not args.carpeta.is_dir():
            raise ValueError('La carpeta no existe. Créala y coloca las fotografías dentro.')
        if args.plantilla and args.final:
            raise ValueError('Crea la plantilla primero; utiliza --final después de completar la referencia.')
        if args.plantilla:
            print('Plantilla creada:', crear_plantilla(args.carpeta))
            print('Completa los números mirando las fotos, antes de ejecutar la lectura automática.')
            return 0
        refs = cargar_referencias(args.carpeta, final=args.final, ajuste=args.ajuste)
        from tutoring.services.handwriting import (
            MODELO, REVISION_MODELO, cargar_modelo, leer_fotografia,
        )
        destino = args.salida or args.carpeta
        if args.salida and any((destino / name).exists() for name in
                               ('resultado_ocr.csv', 'resumen_ocr.json')):
            raise ValueError('La carpeta de salida ya contiene informes. Usa otra para conservarlos.')
        inicio = perf_counter()
        print('Cargando el modelo local una sola vez...', flush=True)
        try:
            cargar_modelo(MODELO, True)
            carga = round(perf_counter() - inicio, 3)
            propuestas, tiempos, diagnosticos = [], [], []
            for ref in refs:
                inicio = perf_counter()
                lectura = leer_fotografia(args.carpeta / ref['archivo'], incluir_diagnostico=True)
                propuestas.append(lectura['propuesta'])
                diagnosticos.append(lectura)
                tiempos.append(round(perf_counter() - inicio, 3))
                print(f'Procesada {len(propuestas)}/{len(refs)}: {ref["archivo"]}', flush=True)
        except (ImportError, OSError, RuntimeError, ValueError) as exc:
            raise ValueError(f'No se completó la evaluación; no se guardaron resultados nuevos: {exc}') from exc
        detalles, resumen = comparar(refs, propuestas, final=args.final)
        resumen.update(modelo=MODELO, revision_modelo=REVISION_MODELO, carga_modelo_segundos=carga)
        resumen['sha256_referencia'] = hashlib.sha256(
            (args.carpeta / 'referencia_ocr.csv').read_bytes()).hexdigest()
        for detalle, segundos, diagnostico in zip(detalles, tiempos, diagnosticos):
            detalle['segundos'] = segundos
            detalle['etapa'] = diagnostico.get('etapa', '')
            detalle['mensaje'] = diagnostico.get('mensaje', '')
            for campo in CAMPOS:
                detalle[f'texto_crudo_{campo}'] = diagnostico.get('lecturas_crudas', {}).get(campo, '')
        destino.mkdir(parents=True, exist_ok=True)
        with (destino / 'resultado_ocr.csv').open('w', newline='', encoding='utf-8-sig') as archivo:
            writer = csv.DictWriter(archivo, fieldnames=list(detalles[0]))
            writer.writeheader()
            writer.writerows(detalles)
        (destino / 'resumen_ocr.json').write_text(
            json.dumps(resumen, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f'Lecturas exactas: {resumen["exactas"]}/{len(refs)} ({resumen["porcentaje_exacto"]} %).')
        print('Resultados: resultado_ocr.csv y resumen_ocr.json, dentro de:', destino)
        if not args.final:
            print('Es un ensayo; no certifica la meta RNF-02 de 50 fotos nuevas.')
        else:
            print('Umbral numérico alcanzado.' if resumen['umbral_numerico_45_de_50'] else 'Umbral numérico no alcanzado.')
            print('La independencia del conjunto, su legibilidad y la revisión humana se documentan aparte.')
        return 0
    except (OSError, ValueError, ImportError) as exc:
        print(f'No se pudo evaluar: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
