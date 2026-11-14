"""Pruebas del calentamiento del lector al arrancar.

Lo que importa comprobar es que está apagado por omisión: encenderlo sin
querer añadiría una carga de modelo de unos 16 segundos a cada orden de
gestión, incluidas las pruebas y las migraciones.
"""
from unittest.mock import patch

from django.apps import apps
from django.test import SimpleTestCase

from tutoring import apps as tutoring_apps


class CalentamientoTests(SimpleTestCase):

    def _config(self):
        return apps.get_app_config('tutoring')

    def test_apagado_por_omision(self):
        with patch.dict('os.environ', {}, clear=False) as entorno:
            entorno.pop('CALENTAR_LECTOR', None)
            with patch.object(tutoring_apps.threading, 'Thread') as hilo:
                self._config().ready()
                hilo.assert_not_called()

    def test_apagado_con_valor_distinto_de_uno(self):
        with patch.dict('os.environ', {'CALENTAR_LECTOR': '0'}):
            with patch.object(tutoring_apps.threading, 'Thread') as hilo:
                self._config().ready()
                hilo.assert_not_called()

    def test_encendido_lanza_un_hilo_demonio(self):
        with patch.dict('os.environ', {'CALENTAR_LECTOR': '1'}):
            with patch.object(tutoring_apps.threading, 'Thread') as hilo:
                self._config().ready()
                hilo.assert_called_once()
                self.assertTrue(hilo.call_args.kwargs['daemon'])
                hilo.return_value.start.assert_called_once()

    def test_un_fallo_al_cargar_no_propaga(self):
        with patch.object(tutoring_apps, 'logger') as registro, \
                patch('tutoring.services.handwriting.cargar_modelo',
                      side_effect=RuntimeError('sin modelo')):
            # No debe lanzar: el aplicativo tiene que arrancar igualmente.
            tutoring_apps._calentar_lector()
            registro.warning.assert_called_once()

    def test_carga_el_modelo_cuando_todo_va_bien(self):
        with patch('tutoring.services.handwriting.cargar_modelo') as cargar:
            tutoring_apps._calentar_lector()
            cargar.assert_called_once_with()