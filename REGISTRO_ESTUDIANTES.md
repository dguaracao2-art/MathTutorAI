# Registro de estudiantes

Ampliación: registro público mediante /crear-cuenta/. Conserva el inicio de
sesión como entrada. Usuario, contraseña y confirmación; sin correo obligatorio
ni recuperación de contraseña. Cada cuenta nueva carece de permisos de personal,
superusuario y grupos. No inicia sesión automáticamente.

## Criterios de aceptación
- Desde Iniciar sesión se puede abrir Crear cuenta y volver.
- Usuario duplicado o inválido y contraseña débil/no coincidente muestran errores.
- Éxito: redirección a iniciar sesión con aviso de cuenta creada.
- Requiere CSRF y utiliza hash y validadores de contraseña de Django.
- No acepta privilegios ni redirecciones externas enviados por el cliente.
- Las cuentas autenticadas vuelven al inicio sin crear otra cuenta.
- Banco común de 53 sumas y progreso propio: no se modifica su implementación.

## Figma y documentación pendientes
Añadir wireframe Crear cuenta con los tres campos, ayuda de contraseña, errores,
botón Crear cuenta y enlace Volver a iniciar sesión. Éxito vuelve al login.
Añadir enlace Crear cuenta al login. Mantener paleta y tipografía acordadas.
Actualizar requisito de gestión de cuentas, historia de usuario, caso de uso y
matriz de trazabilidad preservando la numeración existente. No afirmar que Figma
o el informe ya fueron editados. La arquitectura continúa como monolito Django.
El registro no mejora la exactitud del OCR ni sustituye validación educativa.

## Aplicación local (Git Bash, desde el proyecto y con .venv activa)
git apply --check --ignore-whitespace "/c/Users/Danny Guaraca/Downloads/MathTutorAI_Registro.patch"
git apply --ignore-whitespace "/c/Users/Danny Guaraca/Downloads/MathTutorAI_Registro.patch"
python manage.py test --noinput
python manage.py makemigrations --check --dry-run
python manage.py runserver

No hay migraciones ni dependencias nuevas. Verificar crear estudiante, iniciar
sesión, elegir suma y progreso. No volver a aplicar el parche si ya se aplicó.
Los archivos privados y la base de datos local no se incluyen.

## AWS
Esta entrega no actualiza el servidor. Mantener EC2 detenido durante el trabajo
local. Antes de desplegar: revisar IP pública, actualizar dominio/HTTPS si cambió,
respaldar SQLite con el servicio detenido y transferir solo archivos del cambio;
no sobrescribir .env, settings.py completo ni la base de datos de AWS.
settings.py en AWS contiene configuración de proxy HTTPS que debe preservarse.
Reiniciar mathtutorai tras desplegar. Verificar registro y recorrido de una suma
en HTTPS antes de compartir el enlace. HTTPS publicado previamente no equivale
a validación de todas las funciones. Para apertura pública más amplia, evaluar
limitación de solicitudes y protección contra registros automáticos.
