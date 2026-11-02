# MathTutor AI

Aplicativo de refuerzo de sumas para estudiantes de tercero de EGB. Adapta la idea de práctica guiada, pistas y reintentos de OATutor; no es una copia de su implementación. El proyecto actual utiliza Django y un lector local TrOCR.

## Alcance de esta versión

Una suma vertical por fotografía, dos operandos de 0 a 999 y resultado escrito de hasta cuatro cifras. Incluye sumas con y sin llevadas. Restas, multiplicaciones y ecuaciones quedan fuera del alcance actual.

1. Iniciar sesión con una cuenta de prueba y elegir una suma.
2. Resolverla en papel, capturar o cargar una imagen y revisar su vista previa.
3. Comparar los números propuestos con la hoja, editarlos si hace falta y confirmar. Las pequeñas marcas de llevada se transcriben manualmente cuando son visibles.
4. Comprobar la suma, consultar hasta dos pistas, presentar una corrección y consultar el progreso privado.

Las reglas comprueban los datos confirmados. El lector no recibe la respuesta correcta ni la utiliza para completar una fotografía. Una confirmación manual no cuenta como acierto automático de OCR.

## Ejecutar el proyecto

Conserva tu `.env`, base de datos y fotografías locales. Desde la carpeta de `manage.py`, en Git Bash:

```bash
source .venv/Scripts/activate
python manage.py migrate
python manage.py check
python manage.py runserver
```

Abrir http://127.0.0.1:8000/. Para desarrollo local, `.env` debe definir `SECRET_KEY` propia y `DEBUG=True`. No subir ese archivo a Git. Las dependencias están en `requirements-vision.txt`; si el entorno ya funciona, no hace falta reinstalarlas para esta actualización.

En una instalación nueva se deben aplicar las migraciones y preparar cuentas de prueba y ejercicios desde la administración de Django. No se incluyen credenciales compartidas ni una base de datos personal en los entregables.

## Banco de sumas

El administrador puede añadir o desactivar operaciones en `/admin/tutoring/exercise/`.
Solo indica ambos operandos, entre 0 y 999, y marca «Disponible» para mostrarlas.
El nivel con/sin llevadas se calcula automáticamente. Los estudiantes usan
sus propias cuentas, sin permisos de administración.

Para añadir de una vez las 53 operaciones de práctica incluidas (las tres iniciales y las 50 de desarrollo):

```bash
python manage.py cargar_sumas
```

Se conservan las sumas previas y el progreso; repetir el comando no crea nuevos
duplicados ni reactiva sumas que el administrador haya desactivado. El banco
incluido contiene solo operandos, sin fotos, nombres de archivo ni resultados
escritos. También puede indicarse un CSV propio con `operand_a` y `operand_b`:

```bash
python manage.py cargar_sumas local_ocr/ensayo_png/referencia_ocr.csv
```

El banco presenta diez sumas por página y permite buscar, por ejemplo,
`358 + 167` o `358`. Añadir ejercicios no entrena el OCR, no aumenta su exactitud
y no reduce el tiempo de inferencia.

La web usa el modelo ya descargado en la caché local. Para preparar una caché nueva
sin necesitar fotografías, ejecutar una vez:

```bash
python manage.py preparar_lector
```

Ese comando puede descargar el modelo. No lee fotos ni produce copias de imágenes.
El servidor web carga su propia instancia del modelo al usar el lector por primera
vez; preparar la caché no elimina ese tiempo inicial. `--solo-local` comprueba
la disponibilidad sin permitir descargas.

Para preparar otros equipos o distinguir el uso mediante enlace del desarrollo
local, consultar [COMPARTIR_PROYECTO.md](COMPARTIR_PROYECTO.md).

## Estado y verificación

```bash
python manage.py test --noinput
```

Las pruebas cubren reglas aritméticas, confirmación, autorizaciones, historial, pistas, reintentos, marcas confirmadas y evaluación OCR. El flujo automatizado simula las respuestas del reconocedor; aprobarlo no demuestra precisión del modelo en fotos nuevas.

El último ensayo comunicado antes de esta actualización obtuvo **24/50 lecturas exactas (48%)**. Las fotos ya usadas para ajustar el lector son un conjunto de desarrollo. El 90% de RNF-02 sigue pendiente de comprobar con un conjunto independiente y referencia revisada por dos personas.

- [TUTORIA_SUMAS.md](TUTORIA_SUMAS.md): funcionamiento y comprobación del recorrido.
- [INTEGRACION_LECTURA.md](INTEGRACION_LECTURA.md): lector, formatos y confirmación.
- [EVALUACION_OCR.md](EVALUACION_OCR.md): medición separada de la lectura automática.
- [CIERRE_ENTREGA.md](CIERRE_ENTREGA.md): alcance, evidencias y pendientes reales.

Los estilos se sirven desde el propio proyecto para que la interfaz no dependa de cargar un CDN durante la demostración. Bootstrap 5.3.8 conserva su aviso de licencia MIT en el archivo distribuido.

## Estructura

`accounts/`: acceso y plantilla común. `tutoring/`: ejercicios, intentos, captura, confirmación, reglas y pistas. `tools/`: mediciones locales. `config/`: configuración Django. La carpeta `services/` contiene lógica del mismo aplicativo; no representa microservicios.

No crear una nueva rama para cada comprobación. Continuar en la rama de trabajo existente y revisar sus cambios antes de integrarla. Añadir a Git únicamente los archivos de código y documentación pertinentes; conservar fuera del commit los ZIP de respaldo, `.env`, base de datos, modelos y fotografías personales.
