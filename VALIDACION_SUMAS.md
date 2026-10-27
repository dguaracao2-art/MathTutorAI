# Validación de sumas: casos de referencia RNF-06

## Alcance y resultado

Se añaden 80 casos automáticos con transcripciones numéricas confirmadas:
40 respuestas correctas y 40 incorrectas, sobre 20 sumas sin llevadas y
20 con llevadas aritméticas. Se verifican el estado, la primera columna
discrepante de derecha a izquierda, la marca de revisión y la conservación
del resultado escrito en la presentación.

Los 80 casos pasaron al ejecutar el servicio `sum_review.py` recibido, sin
modificar sus reglas. Las respuestas y columnas esperadas están declaradas
explícitamente en los casos; no se obtienen llamando al servicio evaluado.
La tabla permite revisar y reproducir cada referencia.

No se usan fotografías, OCR ni base de datos. Estas pruebas no validan la
lectura o comprobación de llevadas manuscritas (RF-06/RF-07), la calidad de
las pistas (RF-10), la exactitud OCR (RNF-02), el tiempo web (RNF-01), ni el
piloto educativo. Las llevadas anotadas continúan pendientes; no se debe
presentar esta ejecución como cumplimiento completo de esos requisitos.
El conjunto cubre la parte numérica de RNF-06 y aporta evidencia para RF-07/RF-08.

## Ejecutar

Solo estos casos, con sus 80 identificadores:

```bash
python manage.py test tutoring.test_arithmetic_acceptance --noinput --verbosity 2
```

Suite completa del aplicativo:

```bash
python manage.py test tutoring --noinput
```

Se esperan 125 pruebas si la suite anterior sigue teniendo 45. El número de
pruebas del aplicativo no es una medida de exactitud del OCR. La evaluación
RNF-02 debe usar 50 fotos legibles no utilizadas para ajustar el lector,
con sus transcripciones de referencia, antes de cualquier edición manual.

## Referencias numéricas

Cada fila representa dos casos: la respuesta correcta debe dar `correcto`
y ninguna columna; la incorrecta, `requiere_revision` y la columna indicada.

| Casos | Llevadas aritméticas | A | B | Correcta | Incorrecta | Primera discrepancia |
|---|---|---:|---:|---:|---:|---|
| RNF06-001 / 002 | No | 0 | 0 | 0 | 1 | unidades |
| RNF06-003 / 004 | No | 0 | 7 | 7 | 0 | unidades |
| RNF06-005 / 006 | No | 5 | 0 | 5 | 15 | decenas |
| RNF06-007 / 008 | No | 2 | 3 | 5 | 4 | unidades |
| RNF06-009 / 010 | No | 12 | 6 | 18 | 28 | decenas |
| RNF06-011 / 012 | No | 20 | 30 | 50 | 5 | unidades |
| RNF06-013 / 014 | No | 23 | 14 | 37 | 32 | unidades |
| RNF06-015 / 016 | No | 42 | 16 | 58 | 48 | decenas |
| RNF06-017 / 018 | No | 34 | 25 | 59 | 69 | decenas |
| RNF06-019 / 020 | No | 61 | 28 | 89 | 88 | unidades |
| RNF06-021 / 022 | No | 100 | 200 | 300 | 200 | centenas |
| RNF06-023 / 024 | No | 123 | 234 | 357 | 347 | decenas |
| RNF06-025 / 026 | No | 406 | 152 | 558 | 458 | centenas |
| RNF06-027 / 028 | No | 700 | 80 | 780 | 708 | unidades |
| RNF06-029 / 030 | No | 801 | 98 | 899 | 999 | centenas |
| RNF06-031 / 032 | No | 909 | 0 | 909 | 999 | decenas |
| RNF06-033 / 034 | No | 999 | 0 | 999 | 99 | centenas |
| RNF06-035 / 036 | No | 0 | 999 | 999 | 1999 | unidades de millar |
| RNF06-037 / 038 | No | 111 | 222 | 333 | 303 | decenas |
| RNF06-039 / 040 | No | 321 | 456 | 777 | 177 | centenas |
| RNF06-041 / 042 | Sí | 5 | 7 | 12 | 2 | decenas |
| RNF06-043 / 044 | Sí | 8 | 9 | 17 | 27 | decenas |
| RNF06-045 / 046 | Sí | 9 | 1 | 10 | 0 | decenas |
| RNF06-047 / 048 | Sí | 28 | 17 | 45 | 35 | decenas |
| RNF06-049 / 050 | Sí | 46 | 38 | 84 | 74 | decenas |
| RNF06-051 / 052 | Sí | 59 | 24 | 83 | 82 | unidades |
| RNF06-053 / 054 | Sí | 95 | 7 | 102 | 2 | centenas |
| RNF06-055 / 056 | Sí | 99 | 1 | 100 | 90 | decenas |
| RNF06-057 / 058 | Sí | 99 | 99 | 198 | 188 | decenas |
| RNF06-059 / 060 | Sí | 168 | 257 | 425 | 415 | decenas |
| RNF06-061 / 062 | Sí | 186 | 237 | 423 | 323 | centenas |
| RNF06-063 / 064 | Sí | 555 | 555 | 1110 | 110 | unidades de millar |
| RNF06-065 / 066 | Sí | 999 | 1 | 1000 | 900 | centenas |
| RNF06-067 / 068 | Sí | 999 | 999 | 1998 | 998 | unidades de millar |
| RNF06-069 / 070 | Sí | 875 | 125 | 1000 | 0 | unidades de millar |
| RNF06-071 / 072 | Sí | 450 | 550 | 1000 | 100 | centenas |
| RNF06-073 / 074 | Sí | 678 | 245 | 923 | 913 | decenas |
| RNF06-075 / 076 | Sí | 709 | 291 | 1000 | 1001 | unidades |
| RNF06-077 / 078 | Sí | 908 | 92 | 1000 | 1100 | centenas |
| RNF06-079 / 080 | Sí | 399 | 602 | 1001 | 1 | unidades de millar |

La tabla registra discrepancias observables; no atribuye una causa cognitiva al estudiante.
