import logging
import os
import threading

from django.apps import AppConfig

logger = logging.getLogger(__name__)


def _calentar_lector():
    """Cargar el modelo de lectura en segundo plano al arrancar el servidor.

    Medido en el equipo de desarrollo, cargar TrOCR tarda unos 16 segundos.
    Sin este calentamiento ese tiempo lo paga la primera fotografía que
    alguien suba tras cada reinicio, y esa lectura incumple RNF-01 (10 s)
    aunque todas las siguientes tarden unos 2,4 segundos.

    Se hace en un hilo aparte para no retrasar el arranque: el servidor
    empieza a atender peticiones de inmediato y el modelo queda listo unos
    segundos después. Si alguien sube una fotografía mientras tanto, la carga
    se comparte por el lru_cache de ``cargar_modelo``; nadie espera dos veces.

    Un fallo aquí no debe impedir que el aplicativo arranque: si el modelo no
    está disponible, la lectura informará del problema como siempre.
    """
    try:
        from .services.handwriting import cargar_modelo

        cargar_modelo()
        logger.info("Lector de escritura cargado y listo.")
    except Exception:
        logger.warning(
            "No se pudo precargar el lector; se intentará en la primera "
            "fotografía.", exc_info=True,
        )


class TutoringConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'tutoring'

    def ready(self):
        # Apagado por omisión. Así las pruebas, las migraciones y el resto de
        # órdenes de gestión no cargan un modelo que no van a usar. Se
        # enciende con CALENTAR_LECTOR=1 en el entorno del servidor.
        if os.environ.get('CALENTAR_LECTOR', '').strip() not in ('1', 'true', 'True'):
            return
        hilo = threading.Thread(
            target=_calentar_lector, name='calentar-lector', daemon=True,
        )
        hilo.start()