# Tutoría de sumas: guía vigente

Esta guía sustituye las instrucciones antiguas de actualización por ZIP y creación de ramas. El proyecto ya tiene comprobación, dos pistas, reintentos e historial persistente.

## Recorrido del estudiante

1. Seleccionar una suma del banco y resolverla en papel.
2. Capturar o cargar una foto. La vista previa aparece al seleccionar el archivo, antes de ejecutar el OCR.
3. Comprobar los dos operandos y el resultado escrito. Corregir la transcripción según la foto, no según la respuesta que se espera obtener.
4. Si hay pequeñas cifras de llevada, abrir la sección opcional y transcribir únicamente las visibles. Dejar vacío si no hay marca o no se distingue. No calcular una marca para rellenar el formulario.
5. Confirmar y pulsar **Comprobar mi suma**.
6. Ante **Requiere revisión**, revisar la primera columna indicada de derecha a izquierda, consultar las pistas una por una y volver a fotografiar la corrección.
7. Consultar **Ver mi progreso**. El historial conserva fecha, estado, intentos y pistas de esa cuenta.

Las marcas admiten 0 o 1 sobre decenas, centenas y millares. Son una transcripción manual: el OCR actual no reconoce esas pequeñas anotaciones. Una marca confirmada incorrecta también puede producir **Requiere revisión**, aunque el resultado numérico coincida.

Si la suma se puede separar pero no se reconocen sus números, el formulario permite completarlos manualmente. Una hoja sin una suma identificable pide otra foto. Un fallo técnico del modelo informa que el lector no está disponible; no se convierte en una supuesta lectura correcta.

## Estados

| Estado | Significado |
| --- | --- |
| Lectura pendiente | Hace falta completar la transcripción o presentar una foto que pueda separarse. No es una calificación matemática. |
| Correcto | Los datos confirmados del primer intento coinciden con las reglas de la suma. |
| Requiere revisión | Se encontró una discrepancia verificable en el resultado o en una marca de llevada confirmada. |
| Corregido | Un nuevo intento de la práctica ya coincide. Se conserva el intento anterior. |

Repetir la misma comprobación no crea otro intento. Una foto nueva invalida la confirmación anterior. El historial pertenece a la cuenta y permanece después de cerrar sesión; las fotografías no se guardan en él.

## Comprobación breve en la laptop

Preparar las fotos propias con los valores escritos indicados; no editar la transcripción para aparentar que la fotografía dice otra cosa.

| Caso | Resultado esperado |
| --- | --- |
| 23 + 14, resultado escrito 37 | Correcto. |
| 23 + 14, resultado escrito 32 | Requiere revisión en unidades. |
| Corregir la hoja anterior a 37, cargarla y confirmar | Corregido; nuevo intento visible en el progreso. |
| 28 + 17, resultado escrito 35 | Requiere revisión en decenas. |
| 28 + 17, resultado 45 y llevada visible 1 sobre decenas | Correcto, incluida la marca confirmada. |
| 23 + 14, resultado 37 y marca visible incorrecta 1 sobre decenas | Requiere revisión de esa marca. |
| Hoja vacía, archivo no válido o más de 5 MB | Aviso; no se comprueba una suma inventada. |
| Cámara sin permiso | Aviso y posibilidad de elegir una imagen. |

Revisar también que se ofrezcan solo dos pistas, que cambiar de suma descarte la confirmación anterior y que otra cuenta no vea el progreso propio. Esa comprobación en Chrome de la laptop y del teléfono sigue siendo evidencia manual; los tests del servidor no la sustituyen.

## Validación automática

```bash
python manage.py check
python manage.py test --noinput
```

Las reglas funcionan con y sin llevadas y no revelan la respuesta esperada en la página de error. El catálogo de pistas en `tutoring/services/hints.py` sigue pendiente de revisión docente. No se infieren causas cognitivas a partir de un resultado.
