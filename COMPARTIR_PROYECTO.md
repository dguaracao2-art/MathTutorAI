# MathTutor AI — Guía del equipo, instalación y prueba del prototipo

Versión de la guía: 31 de octubre de 2026. Reemplaza la guía breve anterior.
El prototipo mantiene el alcance de sumas verticales. Esta guía no acredita
requisitos pendientes ni anuncia un despliegue AWS que todavía no existe.

## 1. Qué hace y cómo funciona

El estudiante inicia sesión, elige una suma del banco y la resuelve en papel.
Captura o carga una foto; OpenCV prepara la imagen y separa las filas; TrOCR
propone los números. El estudiante contrasta la propuesta con la hoja, corrige
lecturas equivocadas y confirma. Las reglas aritméticas comprueban los datos
confirmados y localizan la primera discrepancia por columna. Se ofrecen hasta
dos pistas y un reintento; el progreso queda asociado a la cuenta.

El lector no recibe la respuesta correcta para completar una fotografía. Las
pistas actuales proceden de un catálogo de reglas, no de un chat generativo.
La revisión no reconstruye todos los pasos ni identifica automáticamente la
causa cognitiva del error. Las pequeñas marcas de llevada son opcionales y se
transcriben manualmente cuando realmente están escritas en la hoja.

## 2. Qué compartimos y qué permanece separado

| Elemento | Instalaciones locales independientes | Aplicación única en AWS |
| --- | --- | --- |
| Código | Misma versión consolidada para todo el equipo | Una versión instalada en el servidor |
| Banco inicial | Mismos 53 pares mediante cargar_sumas | Un banco central cargado por el responsable |
| Cuentas | Cada instalación crea sus cuentas de prueba | El administrador crea las cuentas de los participantes |
| Progreso | Base de datos propia de cada instalación | Base central; cada cuenta ve su propio historial |
| Fotografías de prueba | Se facilitan aparte; no llegan automáticamente con Git | Cada usuario carga su archivo desde su equipo |
| Modelo OCR | Caché propia de cada instalación | Caché del usuario que ejecuta el servidor |

Los compañeros NO necesitan inventar ni introducir manualmente los 53 ejercicios.
La versión anterior distribuía 50 pares y dependía de tres sumas que ya existían
en la base de Danny. Este ajuste incorpora también 23 + 14, 28 + 17 y 400 + 600:
una base vacía y una base que ya tenía esas sumas pueden disponer del mismo
catálogo. Los identificadores internos pueden ser distintos; se comparan los
operandos, no el número de ID.

El comando añade lo que falte, no duplica pares ya existentes, conserva sumas
personalizadas y no reactiva las que un administrador haya desactivado. Por eso,
si hay ejercicios adicionales o desactivados, el total visible puede diferir.
No se copia la base de datos personal de Danny para igualar el banco.

## 3. Dos formas de participar

### 3.1. Compañero que solo usará un futuro enlace

Necesita navegador moderno, Internet y una cuenta de estudiante. La cámara es
opcional: puede seleccionar una imagen. No instala Python, OpenCV, TrOCR, VS Code
ni YOLO, y no necesita cuenta de AWS. El procesamiento se hará en el servidor.

Todavía no hay un enlace público. La cámara remota requiere HTTPS. La dirección
127.0.0.1 apunta al propio equipo: enviarla a un amigo no le abre la instalación
que está ejecutando Danny.

### 3.2. Compañero que desarrollará o ejecutará el código localmente

Necesita Python 3.12, navegador e Internet para instalar dependencias y preparar
el modelo. Git se utiliza para colaborar por repositorio y VS Code es opcional.
El funcionamiento actual usa CPU y no exige configurar una GPU. No se ha
certificado un mínimo universal de RAM; PyTorch y el modelo deben caber en la
memoria disponible y su rendimiento debe comprobarse en el equipo utilizado.

### 3.3. Herramientas de la asignatura e integración real

Danny aclara que el docente indicó investigar proyectos de visión artificial
con OpenCV y YOLO en Scopus y tener las tecnologías instaladas. No recuerda
una exigencia explícita de integrar todas en este aplicativo. Se atiende la
preparación del entorno de clase y se mantiene pendiente confirmar si YOLO es
un criterio obligatorio de implementación. Que otro grupo lo use no define
por sí solo el requisito de este grupo.

Instalado significa que un paquete está disponible en un entorno Python.
Implementado significa que cumple una función real, invocada y verificada en
el aplicativo. Consultado significa que se revisó como antecedente científico.
La documentación y la exposición deben distinguir los tres estados.

El proyecto utiliza OpenCV y TrOCR. Django REST Framework y YOLO no se presentan
como integrados. Si se exige su integración, se define primero qué requisito
y componente atenderán; instalar un detector genérico no lo convierte en un
lector de dígitos ni resuelve por sí solo la lectura de sumas.

Para los ejercicios académicos se puede preparar otro entorno, fuera del
repositorio, conservando las dependencias de MathTutor AI. Completar primero
la instalación de la sección 5. Después, desde la carpeta del proyecto con su
entorno activo, usando Git Bash:

```bash
mathtutor_project_dir="$PWD"
deactivate
mkdir -p ../Herramientas_Curso
cd ../Herramientas_Curso
py -3.12 -m venv .venv
source .venv/Scripts/activate
python -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
python -m pip install "Django==5.2.18" djangorestframework ultralytics opencv-python
python -c "import cv2, ultralytics, rest_framework; print('OpenCV:', cv2.__version__); print('Ultralytics:', ultralytics.__version__); print('DRF:', rest_framework.VERSION)"
deactivate
cd "$mathtutor_project_dir"
source .venv/Scripts/activate
```

Son instrucciones para preparar el entorno de clase en CPU; esta revisión no
certifica que se hayan ejecutado en todos los equipos. La instalación de YOLO
no descarga necesariamente un modelo adaptado a operaciones manuscritas. Si
la consigna exige estas herramientas dentro del mismo entorno del proyecto,
se comprobará antes la compatibilidad y se actualizarán las dependencias con
pruebas; no mezclar OpenCV gráfico y headless en el mismo entorno por accidente.

AWS es una plataforma en la nube, no una biblioteca Python equivalente a YOLO.
La cuenta y las herramientas de despliegue corresponden al responsable que
publique, según la plataforma elegida. Los usuarios finales no las necesitan.

## 4. Entrega del código

El responsable consolida una versión del repositorio privado y autoriza a los
colaboradores que corresponda. El equipo recibe esa versión completa, no una
colección de parches antiguos para aplicarlos por orden. Los parches de esta
conversación sirven para actualizar la copia del responsable.

El código incluye requirements-vision.txt, las migraciones, los archivos
estáticos, tutoring/data/sumas_practica.csv y esta guía. Se conservan fuera del
paquete la carpeta .venv, .env personal, db.sqlite3 personal y las cachés del
modelo. Las fotografías se entregan por separado si se van a reutilizar.

No crear más ramas para esta comprobación. Primero consolidar la rama existente.

## 5. Instalación nueva en Windows con Git Bash

Abrir la carpeta que contiene manage.py y comprobar Python:

```bash
py -3.12 --version
py -3.12 -m venv .venv
source .venv/Scripts/activate
python -m pip install -r requirements-vision.txt
```

Si el lanzador py no existe, instalar Python 3.12 con su lanzador o utilizar el
intérprete 3.12 confirmado del equipo. No cambiar versiones del proyecto a ciegas.
Si una línea falla, resolver ese error antes de continuar.

Generar una clave para esa instalación:

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Crear .env en la misma carpeta de manage.py y pegar esa clave entre comillas:

```dotenv
SECRET_KEY="pegar_la_clave_generada_en_este_equipo"
DEBUG=True
```

Preparar la base, el banco y la caché:

```bash
python manage.py migrate
python manage.py cargar_sumas
python manage.py preparar_lector
python manage.py createsuperuser
python manage.py check
python manage.py runserver
```

La primera preparación del lector puede descargar archivos del modelo.
preparar_lector no necesita fotografías, no entrena el modelo y no precarga la
memoria de un futuro proceso web: la primera lectura del servidor puede tardar
más al cargar su propia instancia. Para comprobar una caché sin descargar:

```bash
python manage.py preparar_lector --solo-local
```

Abrir http://127.0.0.1:8000/admin/ con el superusuario propio. En Usuarios, crear
cuentas de práctica activas, con contraseña y sin permisos de personal ni de
superusuario. Cerrar la sesión administrativa y entrar por
http://127.0.0.1:8000/ con una cuenta de estudiante.

## 6. Si el equipo ya ejecutaba la versión anterior

Actualizar primero el código y conservar su .env y su base. No crear de nuevo
el entorno, las cuentas ni la base de datos. Para cargar los pares que falten:

```bash
source .venv/Scripts/activate
python manage.py cargar_sumas
python manage.py runserver
```

Repetir cargar_sumas conserva las sumas y los intentos existentes. En una copia
normal con las 53 sumas ya presentes debe indicar cero nuevas. No se requiere
una migración adicional para este ajuste del catálogo.

## 7. Administrar y seleccionar ejercicios

En /admin/tutoring/exercise/ el administrador añade ambos operandos entre 0 y
999 y marca Disponible. La clasificación con/sin llevadas se calcula; no se
introduce manualmente. Es distinta de las pequeñas llevadas que el alumno puede
anotar sobre las columnas en su hoja.

El estudiante usa Buscar una suma: por ejemplo, 358 + 167 o uno de sus números.
La navegación muestra diez ejercicios por página. Antes de cargar una foto,
elegir la misma operación que aparece en ella. Si la foto es de otra operación,
el sistema debe impedir confirmar operandos diferentes del ejercicio elegido.

## 8. Reutilizar las fotografías e01 a e50

Sí se pueden reutilizar como material de desarrollo, regresión y demostración.
No hace falta volver a tomar esas fotografías. Conservar sus nombres reales:
pueden ser e01.jpeg, e01.png u otra extensión admitida según la copia utilizada.

El banco contiene los operandos; no contiene esas fotografías. No hay una
asociación automática entre el ID de una suma y el número del archivo eNN.
Se mira la foto, se busca la operación correspondiente y después se selecciona
el archivo para leerlo. Agregar ejercicios no acelera ni entrena el lector.

Si se comparten, preparar únicamente las fotos matemáticas acordadas, sin
rostros, nombres ni documentos personales. Un compañero puede copiarlas, por
ejemplo, en local_ocr/pruebas_compartidas/ o elegirlas desde otra carpeta.
Compartir fotos no comparte contraseñas ni el historial.

Estas imágenes ya se usaron para ajustar el lector y no acreditan una evaluación
independiente. Si se usa el evaluador, debe conservarse la referencia humana de
cada archivo y el resultado realmente escrito, aunque la suma esté mal resuelta.
No usar la propuesta OCR como referencia ni corregir la referencia para aumentar
el porcentaje. Ninguna corrección manual en la web cuenta como acierto automático.

## 9. Recorrido que el equipo debe comprender

1. Iniciar sesión con cuenta de estudiante.
2. Buscar y elegir la operación de la hoja.
3. Seleccionar una foto existente o capturarla con el permiso correspondiente.
4. Revisar la vista previa antes de solicitar lectura.
5. Comparar ambos operandos y el resultado propuesto con la imagen.
6. Corregir únicamente lo que no corresponda a la hoja y confirmar.
7. Comprobar la suma; si requiere revisión, consultar las pistas en orden.
8. Presentar la corrección y consultar el progreso de esa cuenta.

Si no se separan las filas o el signo, registrar el fallo como limitación de
lectura. Si se propone un dígito equivocado, corregirlo con la imagen. No
cambiar los números de una foto de otra operación para forzar su confirmación.

No se exige una nueva ronda de fotografías para instalar ni ampliar el banco.
Si se realiza una demostración, se puede utilizar material ya disponible.

## 10. Qué es innovador y cómo se describe

Descripción precisa: prototipo funcional de tutor matemático asistido por IA,
inspirado en sistemas de tutoría inteligente (ITS), con comprobación por reglas
y pistas guiadas. No es una implementación de OATutor ni un tutor adaptativo
completo con seguimiento bayesiano del dominio de habilidades.

El problema educativo externo es la necesidad de orientación al practicar
sumas en papel. El aporte propuesto es integrar esa práctica con transcripción
confirmada, revisión por columnas, pistas progresivas, reintentos y progreso
privado. Se presenta como innovación incremental aplicada al contexto; no se
afirma que inventamos los tutores con IA. Su utilidad educativa debe validarse.

Arquitectura: monolito modular con capas lógicas y comunicación cliente-servidor.
Organización interna: MVT. Tecnologías actuales: Django, SQLite, OpenCV y TrOCR.
AWS será una alternativa de alojamiento, no un nuevo estilo arquitectónico.
YOLO y Django REST Framework no están integrados y no se atribuyen al producto.
Si el docente los exige expresamente, se revisará ese requisito antes de cambiar
el alcance; la rúbrica compartida no exige implementarlos ni desplegar.

## 11. Requisitos y evidencia pendiente

| Aspecto | Estado y límite |
| --- | --- |
| Banco, confirmación, comprobación, reintentos e historial | Implementados; las pruebas automáticas no certifican lectura de todas las fotografías |
| Pistas | Dos ayudas por discrepancia; catálogo pendiente de revisión docente, no una tutoría conversacional extensa |
| Lectura de tres campos | Experimental; hubo aciertos y también fallos de separación o de dígitos, incluido 400 + 600 |
| RNF-01: tiempo web | Falta medir el recorrido web bajo las condiciones definidas; tiempo CLI o descarga inicial no lo certifican |
| RNF-02: exactitud | Último ensayo completo comunicado: 24/50, 48 %, anterior a ajustes posteriores; falta validar la meta independiente de 45/50 |
| RNF-03 y RNF-04 | Existen autenticación, historial por cuenta y procesamiento web en memoria; falta comprobar condiciones reales de producción |
| RNF-05: usabilidad con escolares | Piloto con el público objetivo pendiente; una prueba con un adulto no lo sustituye |
| RNF-06: reglas | Batería aritmética automatizada disponible; no equivale a exactitud OCR |
| RNF-07: compatibilidad | Hay evidencia web en escritorio y navegador a tamaño móvil; faltan comprobaciones de equipos físicos previstos, incluido Android |
| Informe y Figma | Alinear capturas, tipografía, alcance solo sumas y mejoras del banco; conservar evidencia histórica como tal |

El informe académico actual evalúa una propuesta integrada y arquitectura
preliminar, sin exigir implementación ni despliegue. Eso no autoriza a declarar
cumplidos requisitos del software que aún no tienen evidencia.

## 12. AWS y prueba de aceptación del piloto

Primero consolidar la versión y la documentación. Después elegir la plataforma
AWS, sus recursos y costo, preparar configuración de producción, HTTPS, servidor
WSGI/ASGI adecuado, archivos estáticos, caché del modelo y persistencia de datos.
No publicar runserver como servidor de Internet ni asumir que subir archivos
convierte automáticamente la instalación local en un servicio disponible.

El administrador del servidor ejecutará migraciones y cargar_sumas una vez para
la base de ese servidor y creará cuentas individuales. Todos usarán ese banco
central; cada usuario conservará únicamente su propio progreso. Las adiciones
locales posteriores no se sincronizan automáticamente con AWS.

En una prueba acotada del piloto, usando archivos existentes, registrar:

- Entrada y salida de una cuenta; otra cuenta no ve el historial ajeno.
- Banco esperado, búsqueda y selección correctas.
- Carga de archivo y alternativa ante permiso de cámara denegado.
- Propuesta de tres campos, corrección humana y comprobación.
- Pistas, reintento y persistencia del progreso al volver a entrar.
- HTTPS, visualización en los equipos previstos y tiempo de respuesta real.
- Qué ocurre ante una lectura fallida y ante solicitudes simultáneas.

El resultado se registra como aprobado, fallido o pendiente por caso. Esa prueba
de aceptación no sustituye el conjunto independiente de RNF-02 ni el piloto
educativo con escolares. No se anuncia un enlace ni un resultado que no existan.

## 13. Avance orientativo para preparar una demostración

Lista explícita de diez frentes; se cuenta la presencia del componente, no su
calidad certificada ni el esfuerzo restante:

| N.º | Frente | Estado de construcción |
| --- | --- | --- |
| 1 | Acceso y cuentas | Construido |
| 2 | Banco y búsqueda | Construido |
| 3 | Captura/carga y vista previa | Construido |
| 4 | Propuesta de lectura y confirmación editable | Construido, con exactitud pendiente |
| 5 | Comprobación aritmética | Construido |
| 6 | Pistas y reintentos | Construido, con revisión docente pendiente |
| 7 | Progreso por cuenta | Construido |
| 8 | Banco inicial reproducible y guía del equipo | Preparado; falta comprobar instalación completa en otro equipo |
| 9 | Informe/Figma reconciliados y versión consolidada | Pendiente |
| 10 | Despliegue y prueba del piloto público | Pendiente |

Ocho de diez frentes preparados equivalen al 80 % de esta lista de construcción.
Es una orientación interna, no el porcentaje de cumplimiento de RF/RNF, la nota
esperada, la precisión OCR ni una estimación del tiempo necesario para terminar.
No incluirlo como una certificación académica de avance global.

## 14. Fuentes y continuidad

- Requisitos, alcance y paleta: informe del proyecto y ACUERDOS_CIERRE_MathTutorAI.md.
- OATutor: https://github.com/CAHLR/OATutor
- Django: https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/
- AWS: https://docs.aws.amazon.com/elasticbeanstalk/latest/dg/create-deploy-python-django.html
- Ultralytics: https://docs.ultralytics.com/quickstart/
- DRF: https://www.django-rest-framework.org/#installation
- PyTorch CPU: https://pytorch.org/get-started/locally/

Se mantiene Python 3.12 y las dependencias del proyecto; no copiar las versiones
antiguas de Django que aparecen en algunos tutoriales de alojamiento.
Para pedir ayuda, comunicar el número de apartado, comando o acción, resultado
esperado, mensaje observado y si se ejecutó localmente o mediante un enlace.
