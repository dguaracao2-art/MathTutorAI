# MathTutor AI: ensayo de lectura manuscrita

Este ensayo se ejecuta en la terminal. Su salida es una propuesta de transcripción
pendiente de confirmación. La conexión con los campos de Django es el siguiente paso.

## Preparar los archivos

Copia la carpeta `tools`, `requirements-vision.txt` y este documento en la raíz de
MathTutorAI, junto a `manage.py`. Trabaja en `feat/lectura-manuscrita` y con `.venv`
activado.

Añade esta línea al final del `.gitignore` existente, conservando su contenido:

```gitignore
/local_ocr/
```

Crea `local_ocr` y coloca dentro las fotografías originales `Img 1.jpeg` y
`Img 2.jpeg`. Esta carpeta contiene entradas y resultados locales de las pruebas.

## Instalar las dependencias

```bash
python -m pip install -r requirements-vision.txt
```

El archivo fija las versiones del ensayo y solicita PyTorch para CPU. OpenCV se
instala con la variante `opencv-python-headless`, apropiada para procesamiento sin
ventanas de escritorio. OpenCV recomienda utilizar una sola variante de su paquete
por entorno. Si el entorno ya tiene otra variante, evita instalar ambas: conserva
una variante compatible y ajusta la línea de OpenCV en este archivo.

La instalación y la primera descarga del modelo pueden tardar varios minutos.
Espera a que vuelva el símbolo `$` antes de ejecutar el comando siguiente.

## Ejecutar la lectura

```bash
python tools/probar_lectura.py "local_ocr/Img 1.jpeg" --reconocer
python tools/probar_lectura.py "local_ocr/Img 2.jpeg" --reconocer
```

Resultados esperados para estas dos muestras:

| Fotografía | operand_a | operand_b | written_result |
| --- | ---: | ---: | ---: |
| Img 1.jpeg | 23 | 14 | 37 |
| Img 2.jpeg | 23 | 14 | 32 |

`pendiente_de_confirmacion` significa que se propone una lectura, todavía sin
confirmación humana ni evaluación aritmética. El segundo resultado debe conservar
32, tal como aparece escrito.

Dentro de `local_ocr/salidas/Img_1` y `Img_2` encontrarás:

- `ubicaciones.png`: localización automática de las tres filas.
- `mascara.png`: tinta seleccionada después de separar el signo y la línea.
- `operando_a.png`, `operando_b.png`, `resultado.png`: recortes enviados al modelo.
- `preparacion.json`: coordenadas y límites del ensayo.
- `lectura.json`: valores propuestos y textos originales producidos por el modelo.

Para revisar solamente los recortes, ejecuta los mismos comandos sin `--reconocer`.
El argumento avanzado `--modelo RUTA` permite usar una copia local compatible.

## Cómo funciona y qué falta probar

OpenCV selecciona tinta azul, estima la inclinación de la línea separadora y busca
el signo +. Después agrupa los trazos por altura y separa dos operandos y un
resultado. Las coordenadas se calculan desde la imagen; el script no recibe la
suma seleccionada ni utiliza números esperados para completar la lectura.

TrOCR reconoce cada recorte por separado. Solo se eliminan espacios del texto
reconocido. Una lectura con símbolos adicionales o fuera del número de cifras
admitido queda pendiente; se conserva el texto original para revisarla.

Alcance inicial: una sola suma vertical, tinta azul, línea separadora visible y sin
llevadas manuscritas adicionales. Estos son límites del ensayo, no el alcance
final del aplicativo. Falta evaluar otros colores, escritores, llevadas visibles,
calidad de captura y fotografías ajenas a sumas con el conjunto del piloto.

La preparación y TrOCR se probaron con las dos fotografías originales: sus seis
campos coincidieron después de normalizar espacios. También se comprobó la
segmentación con cambios de tamaño, márgenes y giros de esas mismas imágenes,
y el rechazo de controles blanco y negro. Se necesita ampliar la evaluación con
imágenes independientes; estas pruebas no establecen una precisión general.

Después de instalar, verifica también el proyecto existente:

```bash
python manage.py check
```

Fuentes del modelo y de OpenCV:

- https://huggingface.co/microsoft/trocr-small-handwritten
- https://pypi.org/project/opencv-python-headless/
