# Cierre del alcance de sumas

## Dos entregables distintos

La rúbrica del componente práctico evalúa una propuesta integrada y una arquitectura tentativa; expresamente no exige implementar ni desplegar. Su cierre documental consiste en completar portada, coherencia de pantallas, anexo de artículos y accesibilidad de enlaces. El informe recibido ya contiene los diez apartados, pero eso no equivale a una calificación perfecta.

El software es un desarrollo adicional del mismo alcance: solo sumas, con dos operandos de 0 a 999, resultado de hasta cuatro cifras y un estudiante como actor directo. Las restas, multiplicaciones y ecuaciones son posibles ampliaciones, sin funciones ni fechas comprometidas en esta versión.

## Cambios reunidos en esta actualización

- Aceptación de JPEG de cámara con imagen auxiliar MPO, usando la imagen principal.
- Vista previa antes de leer la foto y estilos locales compartidos por las pantallas.
- Confirmación manual explícita cuando se aisló la suma pero no se reconocieron sus números.
- Campos opcionales para transcribir marcas visibles de llevada, comprobarlas y conservarlas con el intento. No son reconocimiento automático de marcas.
- Informes OCR separados con `--salida`, etapa de fallo, texto reconocido y huella de la referencia; una carpeta de informe existente no se sobrescribe al usar esa opción.
- Guías actualizadas: ya existe historial persistente y no se requiere crear otra rama.

## Relación con los requisitos

| Área | Estado verificable y límite |
| --- | --- |
| RF-01 a RF-03 | Acceso, banco de sumas e historial privado implementados; el equipo debe preparar las cuentas y ejercicios de su demostración. |
| RF-04 y RF-05 | Captura/carga, validación y vista previa implementadas. Cámara física, permisos y fotos nuevas requieren comprobación en el equipo del usuario. |
| RF-06 | Propuesta editable de tres números y transcripción manual de marcas. El OCR de pequeñas llevadas no está implementado. |
| RF-07 a RF-09 | Reglas sobre datos confirmados, primera discrepancia de derecha a izquierda y estados implementados. |
| RF-10 y RF-11 | Hasta dos pistas, reintentos y persistencia implementados. La revisión docente del catálogo está pendiente. |
| RNF-01 | No demostrado: el tiempo del script no mide el recorrido web ni acredita 29/30 respuestas en 10 segundos. |
| RNF-02 | No demostrado: último ensayo comunicado 24/50 = 48%; las fotos de ajuste no certifican el conjunto final independiente de 50. |
| RNF-03 y RNF-04 | Autenticación, separación por cuenta y procesamiento de fotos sin guardarlas en la ruta web. HTTPS requiere un despliegue real configurado y probado. |
| RNF-05 | Piloto con cinco escolares pendiente. La prueba UX anterior con un adulto se conserva como evidencia distinta. |
| RNF-06 | Existe una batería de 80 casos de reglas, incluida en la suite. No equivale a 80 lecturas manuscritas exitosas. |
| RNF-07 | Verificar en Chrome real de Windows y Android, con tamaños y versiones registrados. Las pruebas automatizadas no certifican todos los equipos. |

No calcular un porcentaje global a partir del número de tests o del 48% de OCR. Un 70-80% solo sería una estimación informal mientras no se defina qué se cuenta como terminado. Los estados anteriores permiten explicar el avance sin presentar pendientes como éxitos.

## Ampliación del banco y preparación para compartir

El banco inicial reproducible reúne 53 operaciones: las tres sumas de demostración
y 50 pares de operandos de las referencias de desarrollo. `python manage.py cargar_sumas` añade solo los que falten, conserva
el estado de disponibilidad de los existentes y no modifica cuentas ni intentos.
El archivo distribuido no incluye fotografías, nombres de imagen ni resultados
escritos. El docente o administrador puede añadir otras sumas desde Django admin.

El banco añade búsqueda por operación o número y navegación de diez ejercicios
por página. Se conserva la paleta y las tarjetas existentes. Es un ajuste de
acceso al banco al aumentar el catálogo: atiende RF-02, HU-02 y CU-02, sin añadir
otro actor, módulo u operación aritmética. Debe registrarse como mejora de la
implementación; no se afirma que el archivo fuente de Figma ya se haya editado.

`python manage.py preparar_lector` permite preparar la caché sin tomar otra foto.
No entrena el modelo ni evita su carga inicial en el proceso del servidor web.
`COMPARTIR_PROYECTO.md` distingue usuarios mediante enlace de colaboradores que
necesitan instalar el código localmente.

La evidencia recibida muestra 28 + 17 confirmado, comprobado y registrado en el
progreso de la cuenta. Las nuevas capturas de 400 + 600 fallaron al separar filas
o aislar el signo. Son una limitación pendiente de RF-05/RF-06 y RNF-02; no se
ocultan del registro ni se convierten en aciertos por añadirlas al banco.
Se detiene la ronda de nuevas fotografías a petición del usuario. La ampliación
del catálogo se verifica con pruebas automatizadas de datos y navegación.

El futuro despliegue en AWS no está ejecutado. Antes de publicar se deben validar
las condiciones de producción y uso remoto; no se anuncia un enlace disponible.

Verificación de esta ampliación: 167 pruebas del proyecto aprobadas; importación
repetida sobre una base aislada con las tres sumas previas, conservando 53
ejercicios; búsqueda y paginación revisadas en Chromium a 1280 y 360 px sin
desbordamiento horizontal. El comando de preparación del modelo se comprobó
con la caché local y sin fotografías. Las pruebas no modifican la base del autor.

## Arquitectura propuesta y decisiones de esta implementación

Se conserva el monolito modular Django, organizado con MVT y lógica de reglas separada de las vistas. No se agregan microservicios, servicios de pago ni otro modelo para esta actualización.

La propuesta contemplaba un directorio temporal de imágenes; la ruta web actual las procesa en memoria y no las guarda, reduciendo su permanencia respecto al máximo de 24 horas de RNF-04. El catálogo actual de pistas reside en Python, mientras la propuesta contempla almacenarlo como contenido. Son decisiones de implementación que deben declararse si se compara el código con la arquitectura tentativa; no cambian las tres funcionalidades ni los cuatro módulos. Si se necesita administrar ese contenido más adelante, deberá revisarse esa persistencia.

## Aplicación en la rama existente

El parche se prepara sobre el ZIP `MathTutorAI_Revision_Cierre.zip` recibido, después del cambio de limpieza de recortes. No contiene tus fotografías, base de datos, claves, modelos ni ZIP de respaldo. Si modificaste los mismos archivos desde ese ZIP, `git apply --check` detectará las diferencias antes de aplicar.

Detener `runserver`. Desde `MathTutorAI`, activar el entorno y ejecutar, ajustando únicamente la ubicación de Descargas si es necesario:

```bash
source .venv/Scripts/activate
git apply --check --ignore-whitespace "/c/Users/Danny Guaraca/Downloads/MathTutorAI_Cierre_Sumas.patch"
git apply --ignore-whitespace "/c/Users/Danny Guaraca/Downloads/MathTutorAI_Cierre_Sumas.patch"
python manage.py test --noinput
python manage.py migrate
python manage.py check
python manage.py runserver
```

La migración añade un campo para marcas confirmadas a los intentos existentes, con un diccionario vacío por defecto. Conserva las cuentas y ejercicios de tu base de datos. No ejecutar de nuevo el parche si ya se aplicó.

Actualizar el navegador con Ctrl+R y realizar el recorrido breve de `TUTORIA_SUMAS.md`. Tras validarlo, revisar `git diff --stat` y preparar un único commit en la rama actual. No usar `git add .` con respaldos dentro del proyecto: añadir los archivos de código y documentación revisados y comprobar que las carpetas privadas sigan ignoradas.

## Medición posterior, sin sobrescribir el ensayo anterior

Solo cuando se decida medir esta versión:

```bash
python tools/medir_exactitud.py local_ocr/ensayo_png --salida local_ocr/mediciones/cierre_01
```

No se debe volver a crear la referencia con `--plantilla` si ya está completa. Este comando continúa siendo un ensayo de desarrollo y no acredita RNF-02. Usar otra carpeta de salida únicamente para una nueva ejecución deliberada; evitar repeticiones sin cambios que justifiquen medir otra vez.
