"""Incorporar operaciones del CSV humano al banco, sin ejecutar OCR."""
import csv
import re
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from tutoring.models import Exercise


class Command(BaseCommand):
    help = ('Añade las operaciones de referencia_ocr.csv al banco, sin duplicar '
            'pares existentes ni modificar su disponibilidad o los intentos.')

    def add_arguments(self, parser):
        parser.add_argument('referencia', type=Path, nargs='?',
                            default=Path(__file__).resolve().parents[2] / 'data' / 'sumas_practica.csv',
                            help='CSV con operandos. Sin ruta, usa las 53 sumas de práctica incluidas.')
        parser.add_argument('--simular', action='store_true',
                            help='Muestra cuántas sumas se añadirían, sin guardarlas.')

    def handle(self, *args, **options):
        # Validar todo antes de modificar la base de datos. El resultado escrito
        # y las imágenes son irrelevantes para definir un ejercicio del banco.
        pairs = []
        seen = set()
        repeated = 0
        try:
            with options['referencia'].open(encoding='utf-8-sig', newline='') as source:
                sample = source.read(4096)
                source.seek(0)
                try:
                    dialect = csv.Sniffer().sniff(sample, delimiters=',;')
                except csv.Error:
                    dialect = csv.excel
                reader = csv.DictReader(source, dialect=dialect)
                if not {'operand_a', 'operand_b'} <= set(reader.fieldnames or []):
                    raise CommandError('El CSV debe tener las columnas operand_a y operand_b.')
                for row in reader:
                    values = [(row.get(name) or '').strip()
                              for name in ('operand_a', 'operand_b')]
                    if any(re.fullmatch(r'[0-9]{1,3}', value) is None for value in values):
                        raise CommandError(
                            f'Fila {reader.line_num}: completa ambos operandos con enteros '
                            'de 0 a 999. No se guardó ninguna suma.'
                        )
                    pair = tuple(map(int, values))
                    if pair in seen:
                        repeated += 1
                    else:
                        seen.add(pair)
                        pairs.append(pair)
        except (OSError, UnicodeError, csv.Error) as error:
            raise CommandError(f'No se pudo leer el CSV: {error}') from error
        if not pairs:
            raise CommandError('El CSV no contiene operaciones. No se guardó ninguna suma.')

        with transaction.atomic():
            existing = set(Exercise.objects.values_list('operand_a', 'operand_b'))
            new_pairs = [pair for pair in pairs if pair not in existing]
            if not options['simular']:
                Exercise.objects.bulk_create([
                    Exercise(operand_a=a, operand_b=b) for a, b in new_pairs
                ])

        verb = 'Se añadirían' if options['simular'] else 'Añadidas'
        self.stdout.write(self.style.SUCCESS(
            f'Operaciones únicas: {len(pairs)}. {verb}: {len(new_pairs)}. '
            f'Ya existentes: {len(pairs) - len(new_pairs)}. Filas repetidas: {repeated}.'
        ))
        self.stdout.write('Se conservaron los ejercicios previos, su disponibilidad y el progreso. '
                          'No se leyeron fotos ni se ejecutó OCR.')
