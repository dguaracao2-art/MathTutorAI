# Detector YOLO para separar las filas de la suma

Añade una ruta alternativa a la separación de filas. No cambia el alcance, los
requerimientos, las historias, los casos de uso ni los módulos: vive dentro de
M2 (captura y lectura), detrás de `preparar_suma`. El estilo arquitectónico
sigue siendo un monolito modular en capas con MVT.

## Qué resuelve

El prototipo distingue dos etapas de fallo: `separacion` y `reconocimiento`.
Hoy la separación la hace OpenCV con umbral de Otsu, detección de la línea con
Hough y componentes conectados. Las fotos inclinadas, con la suma pequeña en
una esquina o con poco contraste fallan ahí, antes de llegar al modelo de
lectura, y el estudiante ve «No pude separar dos operandos y un resultado».

YOLO es un detector de regiones: localiza las tres filas por su apariencia y no
por umbrales de color. TrOCR no cambia; sigue leyendo los mismos recortes.

## Cómo está integrado

`preparar_suma` conserva la cascada de OpenCV tal cual. Cuando las tres pasadas
fallan, y solo entonces, consulta al detector. El detector se usa únicamente si
hay archivo de modelo y ultralytics instalado; en cualquier otro caso el
proyecto funciona exactamente como antes y se conserva el aviso original.

El detector interviene solo como último recurso, después de que las tres
pasadas de OpenCV fallan. Así no puede empeorar una fotografía que el método
actual ya resuelve: en el peor caso no aporta nada.

`separar_con_yolo` devuelve `None` en vez de lanzar errores, de modo que un
fallo del detector nunca interrumpe la lectura. Las cajas detectadas pasan por
`_recortes_con_contraste`, el mismo recorte, margen y normalización que usa la
ruta de tinta tenue.

Interruptores:

| Variable | Valor por defecto | Para qué |
| --- | --- | --- |
| `YOLO_SEPARADOR` | `local_yolo/separador.pt` | Ruta del modelo entrenado |
| `YOLO_CONFIANZA` | `0.25` | Confianza mínima de una detección |

Para desactivarlo basta con retirar o renombrar el archivo del modelo.

## Preparar el conjunto y entrenar

```bash
python -m pip install -r requirements-yolo.txt
python tools/preparar_dataset_yolo.py local_ocr/pruebas
python tools/entrenar_yolo.py
```

La preparación aprovecha la separación con OpenCV: en las fotos que el método
actual resuelve bien, sus cajas se convierten en etiquetas. Las que fallan se
listan al final para etiquetarlas a mano, y son las más valiosas, porque
representan los casos que hoy no funcionan.

Las etiquetas se guardan en el espacio de la imagen sin enderezar, que es el
que recibe el detector al leer una foto nueva, y el entrenamiento añade giros,
desplazamientos y cambios de escala para cubrir hojas inclinadas.

Todo queda en `local_yolo/`, ignorada por Git: fotos, etiquetas, registros y
modelo. No se suben imágenes al repositorio.

## Comprobar antes de usarlo

```bash
python tools/comparar_separacion.py local_ocr/evaluacion_ocr
```

Informa cuántas fotos separa cada método, cuántas recupera el detector y
cuántas pierde. Úsalo con fotografías que no se hayan empleado para entrenar;
en caso contrario el resultado es optimista y no sirve como evidencia.

Si el detector separa menos fotos que OpenCV, retira el archivo del modelo.

## Límites que deben declararse

- Mide separación, no lectura. Separar bien es condición previa para leer, no
  garantía de leer bien. La exactitud sigue midiéndose con
  `tools/medir_exactitud.py` y el umbral de RNF-02 no cambia.
- El conjunto automático hereda los casos que OpenCV ya resuelve. Para que el
  detector aprenda los casos difíciles hay que etiquetarlos a mano.
- Los recortes del detector son en escala de grises con la cuadrícula visible,
  como la ruta de tinta tenue. Los recortes binarios son propios de la ruta de
  OpenCV con tinta bien aislada.
- Entrenar no acredita ningún requisito. Solo la comparación sobre fotografías
  independientes indica si mejora la separación.
- Al cargarse, ultralytics sustituye `PIL.Image.open` por una versión propia que
  busca códecs opcionales. Por eso `modelo_disponible` comprueba el archivo
  antes de importarlo, y `preparar_suma` trata ese `ImportError` como una
  fotografía ilegible, no como un lector caído.

## Resultado medido

Conjunto: las 50 fotografías de `local_ocr/evaluacion_ocr`. El detector se
entrenó con 120 imágenes: 30 de ese conjunto, las que OpenCV ya separaba y
pudieron etiquetarse de forma automática, y 90 fotografías nuevas tomadas
después.

| Método | Fotografías separadas | Porcentaje |
| --- | --- | --- |
| OpenCV, como estaba antes | 30 de 50 | 60 % |
| OpenCV con el detector como rescate | 49 de 50 | 98 % |

Las 20 fotografías que OpenCV no separaba **no se usaron para entrenar**: no se
pudieron etiquetar precisamente porque fallaban. El detector recuperó 19 de
esas 20, y es la única parte de esta medición que es independiente. Las demás
estuvieron en el entrenamiento y no acreditan nada por sí solas.

La fotografía que sigue sin separarse, e15, está escrita en lápiz tenue y ocupa
una parte pequeña de la hoja.

Usado en solitario, el detector separa 48 de 50 y pierde 1 que OpenCV sí
resolvía. Por eso interviene únicamente después de que OpenCV falla: así suma
19 fotografías y no pierde ninguna.

Validación del entrenamiento: precisión 0.973, exhaustividad 0.957 y
mAP50 0.975 sobre 25 imágenes de validación. Esas imágenes salen del mismo
conjunto de entrenamiento, así que describen el ajuste del modelo, no su
comportamiento ante fotografías nuevas.

## Efecto sobre la lectura: medido, y no mejoró

Tras instalar el detector se repitió la medición de lectura sobre las mismas 50
fotografías. El resultado es 24 de 50, igual que antes. La separación mejoró y
la lectura no, y conviene explicar por qué.

Ninguna de las 24 lecturas exactas proviene de las 19 fotografías que el
detector recupera. Las 24 salen de las 30 que OpenCV ya separaba.

| Grupo | Lecturas exactas |
| --- | --- |
| Fotografías que OpenCV separa | 24 de 30 (80 %) |
| Fotografías recuperadas por el detector | 0 de 19 |
| Total | 24 de 50 (48 %) |

El cuello de botella se desplazó: antes el límite era separar la hoja; ahora
casi todas se separan y el límite es reconocer las cifras de las recuperadas.

### Dónde falla, por campo

En las fotografías recuperadas, los aciertos por campo son desiguales:

| Campo | Aciertos |
| --- | --- |
| Primer sumando | 12 de 20 |
| Segundo sumando | 3 de 20 |
| Resultado escrito | 11 de 20 |

El segundo sumando es la fila que tiene el signo + a su izquierda y la raya de
la suma justo debajo. El texto crudo del reconocedor muestra el patrón: para
168 devuelve `11618`, para 26 devuelve `126`, para 238 devuelve `1 2 3181` y
para 76 devuelve `106`. Aparecen unos de más.

La causa, comprobada mirando los recortes que recibe el modelo, es que la raya
de la suma y a veces el signo + quedan dentro del recorte, y el reconocedor los
transcribe como cifras. El detector localiza la fila pero no distingue qué es
cifra dentro de ella, mientras que la ruta de OpenCV sí aísla el signo y la
línea antes de recortar.

### Siguiente paso propuesto

Eliminar la raya y el signo del recorte antes de leerlo, por ejemplo aislando
los trazos horizontales largos y rellenándolos con el fondo. Se intentó una
primera versión y la detección de la raya resultó poco fiable en fotografías
desteñidas, así que queda pendiente de hacer con cuidado y volver a medir.

Mientras tanto, la confirmación del estudiante cubre el caso: la lectura llega
como propuesta editable y esos campos se corrigen a mano.

### Tiempo de respuesta

Sobre las 50 fotografías, el tiempo máximo fue 5,3 segundos y el promedio 2,9.
Ninguna superó los 10 segundos de RNF-01, ni siquiera las recuperadas, que son
las más lentas porque recorren las tres pasadas de OpenCV antes del detector.
Su promedio es 4,0 segundos.

## Lo que esta medición no dice

Mide separación, no lectura. Separar bien es condición previa para leer, pero
no garantiza que TrOCR reconozca las cifras. La exactitud de lectura declarada
hasta ahora, 24 de 50, se midió cuando 20 fotografías ni siquiera llegaban al
modelo; conviene repetirla ahora con `tools/medir_exactitud.py`.

Esa nueva medición necesita fotografías que no se hayan usado para entrenar.
Las 90 nuevas ya entraron al conjunto, así que haría falta un grupo aparte,
tomado después, para que el resultado acredite RNF-02.

## Verificación de este cambio

194 pruebas del proyecto aprobadas, con el modelo presente y sin él. Se añadió
`tutoring/test_yolo_segmentation.py` con el orden de filas, el rechazo de
detecciones inválidas, la tolerancia a fallos del detector y el respaldo a
OpenCV. Dos pruebas de segmentación existentes fijan ahora `usar_detector=False`
porque comprueban detalles propios de la ruta de OpenCV.
