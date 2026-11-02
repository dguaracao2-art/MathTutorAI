# Ajuste de captura de cámara y aclaración de validación

Aplicar después de `MathTutorAI_Reparar_Interfaz.patch`. Conserva la paleta,
la tarjeta centrada y las funciones actuales. No necesita migraciones.

## Evidencia que motiva el ajuste

En la prueba del estudiante, la cámara permitió completar 23 + 14 = 37 y
consultar el progreso. Otras capturas se veían oscuras, inclinadas y con la
operación pequeña dentro de una página completa. También hubo fallos al cargar
archivos: `Img 3.jpeg` no permitió separar las tres filas, mientras `Img 5.jpeg`
propuso 117 donde la hoja mostraba 17. Una propuesta editable no es una lectura
exacta hasta contrastarla con la foto; corregirla manualmente no mejora el
porcentaje de OCR automático.

Se volvió a ejecutar únicamente la separación sobre los tres archivos nuevos:
`Img 3.jpeg` falló; `Img 4.jpeg` e `Img 5.jpeg` se separaron. No se ejecutó el
modelo sobre esos archivos en esta revisión. En el recorte del segundo operando
de `Img 5.jpeg` se observó un trazo corto aislado a la izquierda del 17, que puede
contribuir a la cifra adicional. No se sustituyen números por los del ejercicio.

## Cambios

- Marco azul dentro del video. Se captura solamente la región que indica,
  conservando los números, el signo, la línea y el resultado que el usuario
  coloque dentro. Hay que acercar la hoja para que ocupe buena parte del marco.
- Captura PNG en memoria, sin otra compresión JPEG, sin ampliar imágenes
  pequeñas y con límites de píxeles y peso.
- La captura muestra una vista previa antes del OCR. Si es oscura, está cortada
  o borrosa, se puede repetir; si se ve bien, se pulsa «Cargar y leer fotografía».
- La cámara se apaga después de capturar, al cambiar de archivo, al cerrar,
  ocultar o abandonar la página. Una captura pendiente se descarta si se cierra.
- El aviso de operandos diferentes indica cuál era la suma elegida. Se deben
  transcribir los números reales de la foto; si es otro ejercicio, se vuelve al
  banco. Subir una foto no crea un ejercicio nuevo.

Las llevadas siguen siendo opcionales y manuales: solo se copian las marcas
pequeñas efectivamente escritas sobre las columnas. Los campos vacíos no se
interpretan como una llevada incorrecta. Las marcas confirmadas sí se revisan
junto con el resultado. Esto no representa reconocimiento automático de marcas.

## Verificación y límites

- 153 pruebas Django de web, lógica aritmética, separación y herramientas:
  aprobadas. No se ejecutaron las dos pruebas de inferencia simulada que importan
  PyTorch; el código del lector no se modifica en este ajuste.
- 8 pruebas Node de vista previa, coordenadas de captura, tamaño, permisos,
  cancelación y apagado: aprobadas.
- Chromium real a 1280 y 360 px, con dispositivo de cámara simulado: marco
  contenido, sin desbordamiento horizontal, captura del área indicada, PNG
  visible, tracks liberados y ninguna petición OCR antes de la acción explícita.
- Comprobación y aplicación del parche con archivos CRLF de Git para Windows.

La prueba simulada no evalúa enfoque, iluminación ni calidad de una webcam
física. El nuevo encuadre reduce el fondo enviado al lector, pero no recupera
detalle que la cámara no haya capturado. El formato PNG no añade nitidez a una
imagen borrosa. Permanece la alternativa de cargar una fotografía del teléfono.
No se ha medido una nueva exactitud OCR; se conserva el resultado documentado
de 24/50 (48 %) del ensayo anterior.

## Comprobación breve en el equipo del estudiante

1. Elegir 28 + 17 y escribir esa misma suma con el resultado de la hoja.
2. Abrir la cámara, acercar la hoja al marco azul y capturar con luz uniforme.
3. Revisar la vista previa; repetir si la suma quedó cortada u oscura.
4. Pulsar «Cargar y leer fotografía» y corregir solo las lecturas que no
   coincidan con la foto. Dejar vacías las llevadas si no se anotaron marcas.
5. Confirmar, comprobar y consultar el progreso.

Una captura legible y el mismo flujo mediante archivo bastan para esta prueba
de interacción; no reemplazan una evaluación de exactitud con fotos nuevas.
