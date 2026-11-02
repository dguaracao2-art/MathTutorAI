# Corrección visual y ajuste de pistas

## Motivo

Las capturas de la prueba en Windows mostraron el contenido sin los estilos de Bootstrap: botones sin formato, tarjeta pegada a la izquierda, cámara y fotografías fuera del ancho de la página.

Se reprodujo la causa con `core.autocrlf=true`: Git convirtió los saltos de línea del CSS local a CRLF. El archivo pasó de 232111 a 232116 bytes y dejó de coincidir con el hash de integridad que conservaba la plantilla. El navegador bloqueaba esa hoja de estilos. Las pruebas anteriores del servidor no detectaban ese problema visual.

La corrección elimina ese hash del recurso local y cambia su versión de caché. Bootstrap permanece dentro del proyecto. No se modifica la lectura OCR, las reglas aritméticas, la base de datos ni el historial.

## Cambios de interfaz

La referencia visual sigue siendo la paleta de las páginas 37-38 del informe: azul `#1D4ED8` con texto blanco para acciones principales, naranja suave `#FFF7ED` para pistas, rojo suave `#FEE2E2` para errores, verde `#DCECE7` para confirmaciones y gris `#545454` para texto descriptivo. El ajuste recupera esos usos; no propone una identidad visual nueva ni altera el recorrido de pantallas. Los avisos operativos de carga se distinguen de las tarjetas de pista.

| Elemento | Ajuste | Relación con el diseño |
| --- | --- | --- |
| Contenedor | Tarjeta blanca de hasta 480 px, centrada, con márgenes adaptables. Se retira el símbolo decorativo añadido al título. | Recupera la organización anterior; conserva nombre y colores. |
| Cámara y foto | Tamaño limitado al espacio disponible; cámara de hasta 320 px de alto y foto de hasta 360 px. | Evita desbordamiento y mantiene los controles en el recorrido de captura. |
| Tabla | Cifras alineadas por columnas, tamaño contenido y columna señalada. | Conserva el diagnóstico de la primera discrepancia. |
| Llevadas | Sección opcional con etiquetas separadas y explicación de que puede quedar vacía. | Aclara RF-06; no genera ni reconoce marcas automáticamente. |
| Pistas | Primera pista para localizar; segunda con una acción de conteo, agrupación o revisión de llevada según el caso. | Mantiene el máximo de dos ayudas de RF-10, sin mostrar la respuesta final. |

Ejemplo: para la transcripción 23 + 14 con resultado escrito 32, la primera pista dirige a las unidades. La segunda utiliza las cifras visibles 3 y 4 para proponer empezar por 4 y contar tres pasos. El estudiante calcula y compara con su hoja; la pista no entrega el resultado completo.

El catálogo conserva su condición de borrador pendiente de revisión docente. No se atribuye una causa cognitiva al estudiante ni se añaden operaciones al alcance. Estos ajustes pueden registrarse en UX/UI como corrección visual y mejora de claridad, actualizando únicamente las capturas afectadas después de comprobarlas.

## Aplicación

Este parche correctivo corresponde a la versión que ya recibió `MathTutorAI_Cierre_Sumas.patch`. Se aplica sobre ella, en la misma rama. No volver a aplicar el parche anterior. No requiere migraciones, reinstalaciones ni repetir las 50 fotos del ensayo OCR.

Después de aplicarlo, iniciar el servidor y actualizar Chrome con Ctrl+Shift+R. Comprobar inicio, selección, cámara, fotografía, confirmación, dos pistas y progreso.

## Verificación realizada

Las 155 pruebas de Django siguen aprobadas. Además, se recorrió la interfaz en Chromium 131 con anchos de 1280 y 360 píxeles, sirviendo deliberadamente Bootstrap con saltos de línea Windows. Se comprobó el centrado, la ausencia de desplazamiento horizontal, los límites de cámara y fotografía, la confirmación, las dos pistas, la corrección y el progreso. La cámara y la respuesta OCR de esa prueba fueron simuladas; no se usa como evidencia de exactitud del reconocimiento ni como prueba de un teléfono físico.

Para la foto 23 + 14 = 37 sin números pequeños de llevada escritos arriba, los campos opcionales permanecen vacíos. El historial puede sumar más de dos pistas entre varios intentos; el límite es de dos por discrepancia, no de dos para toda la cuenta.
