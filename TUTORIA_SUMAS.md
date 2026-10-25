# Etapa: comprobación y tutoría de sumas

Este ZIP es una **actualización de 10 archivos** para el proyecto que ya tiene la lectura web de fotografías. Copia su contenido en la carpeta de `manage.py`, combinando carpetas y reemplazando solo los archivos indicados. No modifica la base de datos ni requiere migraciones o paquetes nuevos.

## Qué hace y por qué

1. El estudiante elige una suma, fotografía su hoja y **revisa y confirma** los números que propuso TrOCR. La preparación de la fotografía se hace con OpenCV.
2. Pulsa **Comprobar mi suma**. Las reglas aritméticas del servidor comparan el resultado confirmado con los operandos de la suma elegida. Funciona con operandos de 0 a 999, resultado de 0 a 9999, con y sin llevadas en el cálculo. Nunca usa el resultado correcto para corregir silenciosamente la lectura de la foto.
3. Si hay diferencia, se muestra **Requiere revisión**, la primera columna discrepante de derecha a izquierda y un botón para consultar cada una de las **dos pistas**. Si coincide, se muestra **Correcto**. No se divulga la respuesta esperada en los datos de la página ni se acusa al alumno de una causa que la imagen no prueba.
4. **Capturar mi corrección** solicita una nueva foto de la hoja. Al revisarla, se incrementa el contador del ejercicio y, si la respuesta ya coincide, se muestra **Corregido**. Repetir una misma comprobación no crea otro intento. La selección de otra suma inicia otra práctica.

La orientación está en `tutoring/services/hints.py`: es un **catálogo de borrador**, que un docente debe revisar antes del piloto. Esta etapa no lee ni evalúa las llevadas manuscritas, aunque las reglas sí calculan llevando cuando corresponde. El lector de fotos sigue limitado a una operación vertical clara en tinta azul, signo + y raya separados, sin anotaciones de llevadas. El contador y pistas están en la sesión actual; todavía no existe un historial persistente en la base de datos ni pantalla de progreso. Esa será otra etapa. No hay despliegue AWS, DRF o microservicios en esta entrega.

## Aplicación y prueba en Windows/Git Bash

Partiendo de la rama `feat/lectura-manuscrita` que ya se probó en el navegador, guarda primero esa integración en Git si aún aparece pendiente:

```bash
git status
git add requirements.txt requirements-vision.txt tools tutoring INTEGRACION_LECTURA.md
git commit -m "feat: integrar lectura de fotos con confirmacion web"
git push
git switch -c feat/tutoria-sumas
```

Si `git status` dice `nothing to commit`, omite el `git add` y `git commit` y crea la rama nueva. Si ya guardaste esta integración en un commit anterior, tampoco la repitas.

Cierra `runserver` con `Ctrl+C`, extrae **MathTutorAI_Tutoria_Sumas.zip** en Descargas y pega **su contenido**, no la carpeta contenedora, en `MathTutorAI` junto a `manage.py`. Acepta combinar carpetas y reemplazar archivos coincidentes.

```bash
source .venv/Scripts/activate
python manage.py check
python manage.py test tutoring --noinput
python manage.py runserver
```

Prueba primero la suma **23 + 14**:

- `Img 1.jpeg` → confirma **23, 14, 37** → **Comprobar mi suma** → **Correcto**.
- `Img 2.jpeg` → confirma **23, 14, 32** → **Comprobar mi suma** → **Requiere revisión** en **unidades** → **Pista 1**, **Pista 2**, **Capturar mi corrección** → nueva foto de 37 → **Corregido** e intento 2.
- Prueba **28 + 17** confirmando un resultado escrito **35** en una foto legible con ese mismo ejercicio: debe señalar **decenas**. El reconocedor de fotos no está validado aún para todos los formatos de escritura; se puede editar la propuesta antes de confirmar, siempre respetando lo escrito realmente en la foto.

Las pruebas automáticas usan un lector simulado para el flujo nuevo: comprueban reglas, autorizaciones, cambio de foto, máximo de pistas, reintento y estados. La verificación de la cámara y nuevas fotografías debe hacerse en la laptop. Después de probar, se pueden guardar los archivos de esta rama con `git add tutoring TUTORIA_SUMAS.md`, `git commit -m "feat: revisar sumas y ofrecer pistas progresivas"` y `git push -u origin feat/tutoria-sumas`. Crear el PR es el siguiente paso de revisión grupal.
