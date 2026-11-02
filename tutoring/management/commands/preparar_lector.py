"""Preparar la caché del reconocedor sin necesitar ni procesar fotografías."""
from django.core.management.base import BaseCommand, CommandError

from tutoring.services.handwriting import MODELO, cargar_modelo


class Command(BaseCommand):
    help = 'Descarga o comprueba el modelo fijado por el proyecto, sin leer fotografías.'

    def add_arguments(self, parser):
        parser.add_argument('--solo-local', action='store_true',
                            help='Comprueba la caché sin permitir descargas.')

    def handle(self, *args, **options):
        self.stdout.write('Preparando el lector. La primera vez puede descargar el modelo...')
        try:
            cargar_modelo(MODELO, options['solo_local'])
        except (ImportError, OSError, RuntimeError, ValueError) as error:
            raise CommandError(
                'No se pudo preparar el lector. Comprueba requirements-vision.txt, '
                'la conexión y el espacio de la caché. Detalle: ' + str(error)
            ) from error
        self.stdout.write(self.style.SUCCESS('Modelo disponible en la caché. No se procesaron fotografías.'))
