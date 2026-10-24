# MathTutor AI: lectura de fotografías en la página

Actualización preparada sobre el commit `2b8dfa9`, en la rama
`feat/lectura-manuscrita` (23 de octubre de 2026).

## Qué hace esta actualización

Al pulsar **Cargar y leer fotografía**, Django valida el archivo, separa las tres
filas y ejecuta el lector TrOCR. La página muestra la foto y propone los dos
operandos y el resultado escrito. Todos los números siguen siendo editables.
El usuario debe compararlos con la hoja y pulsar **Confirmar números**.

La segunda fotografía de prueba contiene 23 + 14 con resultado escrito 32.
El lector debe proponer **23, 14 y 32**. Confirmar la lectura conserva el 32;
la comprobación matemática y las pistas corresponden a la siguiente etapa.

Esta sigue siendo una prueba para **una suma vertical, con tinta azul, signo +
separado, raya horizontal y sin llevadas manuscritas adicionales**. Dos fotos
exitosas no demuestran precisión general. Hay que ampliar las pruebas antes de
cubrir el alcance final del proyecto.

## Aplicar en tu computadora

1. Trabaja en `feat/lectura-manuscrita`. El avance anterior ya está en GitHub.
   Si el servidor está corriendo, detén esa terminal con Ctrl+C.
2. Extrae el contenido del ZIP de actualización directamente dentro de
   `MathTutorAI`, en la carpeta que contiene `manage.py`. Acepta combinar las
   carpetas y reemplazar los archivos incluidos. Conserva las otras carpetas.
3. En Git Bash, desde MathTutorAI, ejecuta uno por uno:

```bash
source .venv/Scripts/activate
python -m pip install -r requirements-vision.txt
python -m pip check
python manage.py check
python manage.py test tutoring --noinput
```

La instalación ahora incluye las dependencias de Django y de visión desde un
solo comando. Se unificó Pillow en 12.3.0: antes un archivo pedía 13.0.0 y el
otro exigía una versión menor que 13. No se agregaron migraciones.
Las pruebas automáticas usan una base temporal y propuestas simuladas; no
modifican tu base de ejercicios ni descargan el modelo.

4. Inicia el servidor:

```bash
python manage.py runserver
```

Entra al aplicativo en http://127.0.0.1:8000/, inicia sesión y elige **23 + 14**.
Si la página ya estaba abierta, actualízala con Ctrl+R.

## Comprobar en la página

| Acción | Resultado esperado |
| --- | --- |
| Cargar `Img 1.jpeg` | Campos propuestos: 23, 14 y 37. |
| Confirmar esa lectura | Mensaje informativo con el resultado escrito 37. |
| Seleccionar `Img 2.jpeg` | Se limpian la vista previa, los campos y el aviso anteriores. |
| Cargar esa segunda foto | Campos propuestos: 23, 14 y 32. |
| Confirmarla | Conserva el 32, sin marcar la suma como matemáticamente correcta. |
| Cambiar temporalmente el segundo número a 15 y confirmar | Pide revisar porque no coincide con el ejercicio elegido. Volver a 14 permite confirmar. |
| Cargar una hoja en blanco | Muestra lectura pendiente y pide otra fotografía; no habilita confirmación. |
| Actualizar la página | Mantiene el ejercicio elegido; vuelve a pedir cargar la foto. |

Una lectura parcial deja vacíos los números que no pudo interpretar. Una foto
sin una suma identificable no habilita el formulario de confirmación.
Las imágenes de otros estilos pueden quedar pendientes porque el lector aún
está en una fase experimental. La captura de cámara usa el mismo flujo de carga.

La primera lectura después de iniciar Django puede tardar más mientras carga
el modelo en memoria. Después lo reutiliza dentro del mismo proceso. Si está
ocupado, pide esperar y volver a cargar la foto.

## Si aparece «El lector no está disponible»

Revisa el mensaje de la terminal de Django. La web utiliza el modelo ya guardado
en la caché local, sin iniciar descargas durante una carga de foto. Si el modelo
falta (por ejemplo, en la computadora de un compañero), detén el servidor y
prepara la caché una vez con una fotografía de prueba:

```bash
python tools/probar_lectura.py "local_ocr/Img 1.jpeg" --reconocer
```

Este comando conserva la prueba por terminal y puede descargar el modelo.
Cuando termine, vuelve a ejecutar `python manage.py runserver`.

## Por qué se modifican estos archivos

| Archivo | Responsabilidad |
| --- | --- |
| `tutoring/services/handwriting.py` | Comparte la preparación y lectura entre la terminal y Django; reutiliza el modelo y no recibe la respuesta esperada. |
| `tutoring/views.py` | Devuelve la propuesta y verifica que la confirmación corresponde a la misma foto, sesión y ejercicio. |
| `tutoring/static/tutoring/photo_upload.js` | Carga la imagen, presenta los avisos y descarta respuestas de fotos anteriores. |
| `tutoring/static/tutoring/sum_confirmation.js` | Completa los campos, permite editar y envía la confirmación. |
| Las dos plantillas de ejercicio/confirmación | Explican la revisión de números y el alcance de la captura. |
| `tools/probar_lectura.py` | Sigue ofreciendo la prueba por terminal, usando el mismo servicio. |
| Los dos archivos `requirements` | Instalan versiones compatibles entre sí. |
| `tutoring/test_photo_reading.py` | Comprueba el flujo, los límites de los campos y los errores de sesión, foto y lectura. |

`services` es una carpeta de lógica reutilizable dentro del mismo aplicativo
Django. La foto se procesa durante la petición; la ruta web no guarda copias
ni genera `local_ocr/salidas`. Los resultados de la prueba por terminal sí
permanecen en la carpeta local ignorada por Git.

El comprobante de lectura es firmado por Django y vence a los 30 minutos.
Contiene la huella de la foto, el ejercicio y la propuesta, no la fotografía.
La confirmación registra si la propuesta se aceptó (`ocr_confirmed`) o se
corrigió (`ocr_edited`). No es una evaluación de la suma.

## Guardar después de las pruebas manuales

Cuando las dos fotos funcionen en tu navegador, revisa los cambios y guarda
esta misma rama. Ejecuta los comandos uno por uno:

```bash
git diff --stat
git add requirements.txt requirements-vision.txt tools/probar_lectura.py tutoring/services tutoring/views.py tutoring/static/tutoring/photo_upload.js tutoring/static/tutoring/sum_confirmation.js tutoring/templates/tutoring/exercise_detail.html tutoring/templates/tutoring/_sum_confirmation.html tutoring/test_photo_reading.py INTEGRACION_LECTURA.md
git commit -m "feat: integrar lectura de fotos con confirmacion web"
git push
git status
```

El Pull Request puede prepararse después de revisar la prueba en tu laptop.

## Validación de esta actualización

- 29 pruebas automáticas de Django aprobadas y comprobación del proyecto sin errores.
- 7 pruebas de interacción JavaScript aprobadas con un DOM simulado.
- Carga y confirmación reales mediante el cliente de pruebas de Django y TrOCR: las
  dos fotos originales produjeron 23/14/37 y 23/14/32. Ambas se confirmaron sin
  alterar el resultado escrito.
- Una hoja blanca y una captura del explorador de archivos quedaron en lectura
  pendiente, sin habilitar confirmación.
- Se comprobó la reutilización del modelo dentro del mismo proceso.

Queda por verificar la interacción en el navegador de la laptop y ampliar el
conjunto de fotos, escrituras y condiciones de captura.
