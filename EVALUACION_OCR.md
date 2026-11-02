# Evaluación de exactitud de lectura — RNF-02

La herramienta `tools/medir_exactitud.py` compara la propuesta automática de
ambos operandos y el resultado escrito con una transcripción humana previa.
Una foto es exacta solo si coinciden los tres números. Un campo vacío o una
lectura incompleta cuenta como fallo; ninguna foto evaluada se elimina del total.
No se corrige la respuesta matemática del estudiante: si escribió 32, esa es
la referencia, aunque el resultado correcto de la suma fuera 37.

## Preparación de la referencia

Conserva las fotos anteriores en `local_ocr/pruebas/`, como conjunto de ajuste
y regresión. No sirven para acreditar RNF-02, pues se usaron para mejorar el lector.

Para un ensayo del procedimiento pueden utilizarse fotos conocidas en otra
carpeta dentro de `local_ocr/`. Para la evaluación final prepara
`local_ocr/evaluacion_ocr/` con 50 fotos nuevas: 25 sumas sin llevadas y 25
con llevadas aritméticas. Usa distintos números y formas de escritura,
incluyendo resultados correctos e incorrectos, dentro del alcance del aplicativo.
Las llevadas pequeñas manuscritas siguen pendientes de reconocimiento y
deben documentarse como una limitación de RF-06/RF-07.

Las fotos deben contener una sola suma legible, sin nombres ni rostros,
en JPG o PNG de hasta 5 MB. Dos revisores deben transcribir independientemente
los tres números sin consultar al OCR y acordar la referencia antes de medir.
No se debe cambiar una referencia para que coincida con lo reconocido.

Después de colocar las fotos en la carpeta, genera la plantilla una sola vez:

```bash
python tools/medir_exactitud.py local_ocr/evaluacion_ocr --plantilla
```

Completa `referencia_ocr.csv` mirando las fotos. Puedes abrirlo en VS Code o
en un editor de CSV. Admite coma o punto y coma; conserva los encabezados:

```csv
archivo,operand_a,operand_b,written_result
foto01.jpg,23,14,32
```

La fila es solo un ejemplo del formato, no un dato para copiar en la evaluación.
La plantilla deja los números vacíos y nunca sobrescribe una referencia existente.
Si después añades fotos, incorpora sus filas a la referencia antes de evaluar.
Los operandos admiten 0–999 y el resultado escrito 0–9999.

## Ejecución y resultados

Ensayo, sin acreditar la meta de 50 fotos:

```bash
python tools/medir_exactitud.py local_ocr/ensayo_png --salida local_ocr/mediciones/ensayo_01
```

Evaluación final, una vez completadas y revisadas las 50 referencias:

```bash
python tools/medir_exactitud.py local_ocr/evaluacion_final --final --ajuste local_ocr/ensayo_png --salida local_ocr/mediciones/final_01
```

El modo final exige 50 referencias, 25 por tipo, los archivos correspondientes,
ninguna foto duplicada por bytes y ninguna copia idéntica del conjunto de ajuste.
Si ese conjunto está en otra carpeta, indícalo con `--ajuste RUTA`.
La comparación de huellas no detecta recortes o versiones recomprimidas: el
equipo debe garantizar que las fotos sean nuevas y no utilizadas para ajustar.

Se guardan `resultado_ocr.csv` (comparación por foto y campo, etapa, mensaje y texto
reconocido) y `resumen_ocr.json` (totales, grupos, modelo, revisión y SHA-256 de la
referencia). Con `--salida` se escriben en la carpeta indicada y se rechaza una
carpeta que ya contenga informes: así se conserva la medición anterior.
Sin `--salida` se mantiene el comportamiento antiguo: se guardan en la carpeta
evaluada y una repetición reemplaza esos informes, conservando la referencia.
Un fallo de carga o ejecución del modelo aborta la medición; no se presenta
un conjunto parcial como evaluación completa. Si falla una ejecución, no uses
reportes antiguos que pudieran quedar de otra ejecución.

La meta numérica exige al menos 45 fotos exactas de 50. El script comprueba
ese umbral; la legibilidad, revisión por dos personas e independencia del
conjunto se documentan aparte. No se debe afirmar que RNF-02 se cumplió
solo por instalar la herramienta o por ejecutar ensayos con las fotos de ajuste.
Los tiempos del script son locales: no acreditan el tiempo de respuesta web RNF-01.

## Privacidad y control de versiones

```bash
git check-ignore local_ocr/
git ls-files local_ocr/
```

El primero debe mostrar la carpeta; el segundo debe quedar vacío. Las fotos,
referencias y resultados locales permanecen allí y no se añaden al repositorio.
El comando ejecuta el modelo ya descargado, sin enviar las fotos a una API.

Pruebas del evaluador, sin descargar modelos ni usar fotografías personales:

```bash
python manage.py test tutoring.test_ocr_evaluation --noinput
```

## Estado de las fotografías ya utilizadas

El último ensayo comunicado antes de la actualización de cierre obtuvo 24/50
lecturas exactas (48%). Las 50 fotos ya utilizadas para ajustar el lector son
ahora un conjunto de desarrollo. Cambiar su formato a PNG o corregir manualmente
un campo no las convierte en una evaluación independiente. La confirmación
manual en la web no modifica la propuesta automática comparada por este script.

No se ha medido aquí la exactitud de la actualización nueva. Para estudiar los
fallos, el CSV distingue `separacion` de `reconocimiento` y conserva el texto
crudo. No es necesario volver a generar un diagnóstico mediante código pegado
en la terminal después de cada ensayo.

## Ajuste de contraste para capturas tenues

Después del ajuste del marco de cámara, se reprodujo una lectura incorrecta
en `foto_prueba.png`: la propuesta era 8, 17, 45, aunque la hoja mostraba
28, 17, 45. El recorte conservaba el primer número, pero el fondo gris y la
cuadrícula también se intensificaban al aplicar autocontraste global.

La ruta de tinta tenue ahora estima el fondo local con un cierre morfológico
y normaliza la iluminación mediante división. Conserva las cajas, el orden de
los campos y los trazos de la imagen. La ruta binaria de tinta bien aislada
permanece igual. No hay reglas para sustituir 8 por 28, 47 por 17 ni para
completar números usando el ejercicio seleccionado o la suma calculada.

La comparación local utilizó el mismo modelo y revisión fijados en el código,
con inferencia real en CPU, sobre 39 fotografías disponibles: e16–e50,
Img 3, Img 4, Img 5 y foto_prueba. En foto_prueba la nueva propuesta fue
28, 17, 45. En las otras 38 fotografías no cambiaron las propuestas ni los
fallos de separación; los recortes que llegaban al modelo fueron idénticos.
Img 3 siguió fallando al separar filas e Img 5 siguió proponiendo 117 en lugar
de 17. El cambio tiene alcance limitado y no resuelve todas las capturas.

Estas fotos son de desarrollo, no una evaluación independiente. El 48 %
documentado arriba corresponde al ensayo anterior de 50 fotos; esta comparación
parcial no constituye una nueva medición sobre ese conjunto ni certifica RNF-02.
Los resultados previos deben conservarse. Las correcciones manuales en la web
siguen distinguiéndose de los aciertos automáticos.

Verificación de esta actualización: 157 pruebas de `tutoring` aprobadas y
lectura real de foto_prueba mediante `leer_fotografia`, con propuesta
28, 17, 45. El parche contiene el lector, sus pruebas y este documento;
se aplica después de los ajustes de interfaz y cámara en la misma rama.
