# Lectura de fotografías y confirmación

## Implementación actual

Django valida la fotografía, separa las tres filas y ejecuta TrOCR local. El usuario revisa y confirma la propuesta antes de comprobar la suma. El historial y la tutoría ya están implementados: su guía está en `TUTORIA_SUMAS.md`.

El lector es experimental. Admite una suma vertical clara en tinta azul, signo + separado y una raya debajo de los operandos. Los límites de entrada son 5 MB y 20 megapíxeles. Los archivos JPG de cámara que Pillow identifica internamente como MPO se abren usando su imagen principal; no se cambia el original ni se lee su imagen auxiliar.

La vista previa aparece al seleccionar la foto. Las lecturas parciales dejan vacíos sus campos. Si se aisló la suma pero todos los números quedaron vacíos, se permite completarlos mirando la hoja y la confirmación se identifica como manual. Si falla la separación, se pide otra foto. Los números confirmados nunca se usan para incrementar la exactitud del OCR.

Las llevadas pequeñas se transcriben manualmente en tres campos opcionales. La lectura automática de estas marcas permanece pendiente. No se debe presentar la suma aritmética con llevadas como evidencia de reconocimiento automático de sus anotaciones.

## Separación entre lectura y comprobación

`tutoring/services/handwriting.py` no recibe operandos esperados ni la respuesta del ejercicio. `sum_review.py` comprueba los datos confirmados por el estudiante. El resultado escrito de una foto puede estar equivocado y debe conservarse al transcribir; por ejemplo, leer 23 + 14 con resultado escrito 32 no debe convertirse automáticamente en 37.

La confirmación exige un comprobante firmado, asociado a la sesión, usuario, ejercicio y huella de la fotografía, que vence a los 30 minutos. Los operandos confirmados deben coincidir con la suma elegida. Cambiar la foto obliga a confirmar nuevamente.

## Modelo y privacidad

El modelo se carga una vez por proceso y se reutiliza; la web no inicia descargas durante una petición. Las inferencias de un mismo proceso se serializan. Una petición que encuentra el lector ocupado recibe un aviso para volver a intentarlo.

La fotografía se procesa en memoria durante la petición y no se guarda en la base de datos. La vista previa usa una URL temporal del navegador que se revoca al cambiar la imagen o salir de la página. El historial conserva los números y las marcas confirmadas, no las fotos. Las salidas creadas explícitamente por las herramientas de terminal permanecen en la carpeta privada `local_ocr/`.

El último ensayo comunicado obtuvo 48% de lectura exacta antes de esta actualización. Se necesita una nueva medición para conocer el efecto de estos cambios; no se atribuye aquí un porcentaje nuevo. Los avisos del modelo y los tiempos locales no sustituyen las mediciones RNF-01 y RNF-02.

## Mantenimiento

Conservar las dependencias existentes y la misma rama de trabajo. Ejecutar `python manage.py test --noinput` para las regresiones del servidor. Consultar `EVALUACION_OCR.md` para medir OCR sin mezclarlo con la edición manual.
