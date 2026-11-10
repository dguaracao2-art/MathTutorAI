# API REST de MathTutor AI

Expone los módulos M2, M3 y M4 como servicio HTTP, con Django REST Framework.
Es una interfaz adicional sobre los mismos servicios: no duplica reglas, no
amplía el alcance y no cambia el estilo arquitectónico.

## Qué cambia y qué no

| Elemento | Efecto |
| --- | --- |
| Alcance: solo sumas, dos operandos de 0 a 999 | Sin cambios |
| RF-01 a RF-11 y RNF-01 a RNF-07 | Sin cambios |
| HU-01 a HU-05, CU-01 a CU-08 | Sin cambios |
| Módulos M1 a M4 | Sin cambios |
| Estilo: monolito modular en capas, cliente-servidor | Sin cambios |
| Patrón interno MVT | Sin cambios; la API es otra entrada a la misma capa de lógica |
| Tabla de tecnologías | Añadir Django REST Framework |
| Sección 9.3, componentes | Una línea: M2, M3 y M4 exponen además una interfaz REST |

Las páginas web siguen funcionando igual. La API no las sustituye todavía.

## Rutas

Todas requieren sesión iniciada, la misma de la práctica (RNF-03). No se
añadieron tokens ni otro mecanismo de autenticación. El límite es de 60
peticiones por hora y usuario, porque el lector atiende una foto a la vez.

### POST /api/v1/lecturas/

M2. Recibe `fotografia` como multipart y devuelve la propuesta de los tres
números. No comprueba la suma: la respuesta incluye
`confirmacion_requerida: true`.

```json
{
  "estado": "pendiente_de_confirmacion",
  "etapa": "reconocimiento",
  "propuesta": {"operand_a": 23, "operand_b": 14, "written_result": 37},
  "can_confirm": true,
  "confirmacion_requerida": true,
  "mensaje": "Lectura lista. Revisa los tres números con tu fotografía y confírmalos."
}
```

Responde 400 si la imagen no cumple los límites (JPG o PNG, 5 MB, 20
megapíxeles) y 503 si el lector está ocupado o no disponible.

### POST /api/v1/revisiones/

M3. Recibe los números **ya confirmados** y devuelve el estado y la primera
columna discrepante. Nunca devuelve el resultado correcto.

```json
{"operand_a": 28, "operand_b": 17, "written_result": 35}
```
```json
{
  "estado": "requiere_revision",
  "columna": "decenas",
  "tipo_de_discrepancia": "result",
  "pistas_disponibles": 2
}
```

Admite `carries`, las marcas de llevada transcritas a mano, por ejemplo
`{"decenas": 1}`. Solo 0 o 1, y solo en decenas, centenas o unidades de millar.

### POST /api/v1/pistas/

M4. Entrega una sola pista del catálogo revisado. `numero` es 1 o 2.

```json
{"operand_a": 28, "operand_b": 17, "written_result": 35, "numero": 1}
```

Responde 400 si se pide una tercera pista y 409 si la suma confirmada no tiene
discrepancias. Las pistas no revelan el resultado.

## Por qué así

La comprobación parte siempre de números confirmados, igual que en la web: la
API no permite comprobar una lectura automática sin confirmar. El máximo de dos
pistas se conserva, y se entregan de una en una para no adelantar la segunda
ayuda. El registro del intento sigue a cargo de la vista web; la API no crea
intentos.

## Relación con un posible microservicio

Esta API es el primer paso si más adelante se separa el lector en un servicio
propio. El lector es el componente pesado: carga un modelo en memoria y
condiciona RNF-01, mientras el resto de la aplicación es ligero. Exponerlo por
HTTP permite medirlo y, si las pruebas lo justifican, moverlo sin tocar los
módulos que lo consumen.

Hoy no hay microservicios: todo es un mismo despliegue, como indica la
sección 9.1 del informe. La separación sigue siendo una alternativa
condicionada a las pruebas, como ya dice la sección 9.6.

## Verificación

194 pruebas del proyecto aprobadas. `tutoring/test_api.py` cubre el rechazo sin
sesión, la suma correcta sin pistas, la discrepancia con su columna, las dos
pistas entregadas por separado, la ausencia de una tercera, los números fuera
de alcance, las marcas de llevada, el lector ocupado y la fotografía no admitida.

Comprobación manual, con el servidor en marcha y sesión iniciada en el
navegador: abrir http://127.0.0.1:8000/api/v1/revisiones/ muestra el formulario
navegable de DRF para enviar una prueba.
