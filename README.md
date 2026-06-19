# BOT Gestión de Vacaciones 🤖🌴

**Trabajo Práctico Integrador - Organización Empresarial**

--------------------------------------------
Equipo de Desarrollo (Comisión 8)
_-------------------------------------------
    Christian Herrero
    Bruno Sosa

## 📌 Descripción del Proyecto
Este proyecto consiste en un Bot de Telegram diseñado para automatizar y gestionar el proceso de solicitud de vacaciones de los empleados de una organización. El sistema interactúa directamente con una base de datos en Google Sheets para verificar la disponibilidad de días, cruzar fechas con compañeros del mismo sector para evitar superposiciones y registrar los estados de las solicitudes (Aprobación Automática o Derivación a RRHH).

## 🗂️ Estructura del Repositorio

El proyecto tiene la siguiente estructura de directorios y archivos:

CHATBOT/
│
├── codigo/
│   ├── .env.example          # Plantilla para la variable de entorno del Token
│   └── bot_vacaciones.py     # Script principal del bot de Telegram
│
├── documentos/
│   ├── diagrama bpmn - grupo 19.png  # Diagrama del proceso de negocio
│   └── Manual de usuario.txt         # Instrucciones de uso para el usuario final
│
├── .gitignore                # Reglas de exclusión para GitHub
├── README.md                 # Este archivo
└── requirements.txt          # Dependencias y librerías de Python requeridas

🔒 Nota de Seguridad: Por políticas de buenas prácticas, los archivos con credenciales reales (.env con el token de Telegram y credenciales.json con los accesos a Google Cloud) han sido excluidos del repositorio público. Estos archivos se proveen por separado en un archivo ZIP adjunto a la entrega.

--------------------------------------------
⚙️ Requisitos Previos (requirements.txt)
--------------------------------------------

Asegúrese de tener instalado Python 3.8 o superior. Las librerías necesarias para ejecutar el programa son:

    python-telegram-bot (Interacción con la API de Telegram)

    gspread (Conexión y lectura/escritura en Google Sheets)

    oauth2client (Autenticación con la API de Google Cloud)

    python-dotenv (Gestión de variables de entorno ocultas)

Podes instalarlas ejecutando en consola el siguente comando:
    pip install -r requirements.txt

--------------------------------------------
🚀 Guía de Despliegue y Ejecución
--------------------------------------------

Para ejecutar el programa localmente o evaluar el trabajo práctico, siga estos pasos:

    1- Clonar el repositorio o extraer el contenido en su computadora.

    2- Configurar Credenciales:

    2.1- Extraiga el archivo credenciales.json (provisto en el ZIP adjunto) y colóquelo en la carpeta raíz CHATBOT/.

    2.2- En la carpeta codigo/, renombre el archivo .env.example a .env y pegue dentro el Token proporcionado en la entrega. 
    
        Debería quedar así: TELEGRAM_TOKEN=token_proporcionado_aqui.

    3- Abrir una terminal y navegar hasta la carpeta codigo/:

        > cd CHATBOT/codigo

    4- Instalar las dependencias (si no lo hizo en el paso anterior):
        pip install -r ../requirements.txt

    5- Ejecutar el bot:
        python bot_vacaciones.py

    (Si usa Mac, puede ingresar "python3 y arrastrar el archivo bot_vacaciones.py a la terminal y ejecutar")

    6- Interactuar: Abra Telegram y envíe el comando /vacaciones al bot para iniciar el flujo.


# 📊 Estructura de la Base de Datos (Google Sheets)

El sistema utiliza un documento de Google Sheets como base de datos relacional, compuesto por dos hojas principales en el mismo archivo:

┌──────────────────────────────────────────────────────────────────────────────┐
│                        📄 empleados                                          │
├──────────────────┬───────────────────────────────────────────────────────────┤
│ Campo            │ Descripción                                               │
├──────────────────┼───────────────────────────────────────────────────────────┤
│ id_empleado      │ Identificador único                                       │
│ nombre_apellido  │ Nombre completo del empleado                              │
│ dias_disponibles │ Saldo de días de vacaciones disponibles                   │
│ email            │ Correo electrónico del empleado                           │
│ area             │ Departamento o área de trabajo                            │
│ fecha_ingreso    │ Fecha de ingreso a la empresa                             │
└──────────────────┴───────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────┐
│                  📄 solicitud_de_vacaciones                                  │
├────────────────────┬─────────────────────────────────────────────────────────┤
│ Campo              │ Descripción                                             │
├────────────────────┼─────────────────────────────────────────────────────────┤
│ id_solicitud       │ Identificador único de la solicitud (PK)                │
│ id_empleado        │ Referencia al empleado (FK → empleados)                 │
│ fecha_inicio       │ Fecha de inicio de las vacaciones                       │
│ fecha_fin          │ Fecha de fin de las vacaciones                          │
│ dias_solicitados   │ Cantidad de días solicitados                            │
│ estado_tramite     │ Estado: Pendiente, Aprobado, Rechazado, etc.            │
│ fecha_solicitud    │ Fecha en que se realizó la solicitud                    │
│ observaciones      │ Notas o comentarios adicionales                         │
│ chat_id            │ ID del chat para notificaciones                         │
│ notificado         │ Booleano: ¿Ya fue notificado el estado?                 │
└────────────────────┴─────────────────────────────────────────────────────────┘

## Esqueleto de Navegación

                 [ ESTADO INICIAL: ESPERA ]
                  /                     \
          (Comando /vacaciones)       (Comando /rrhh_notificar)
                /                                 \
        [ESPERANDO_LEGAJO] 
        [COMPUERTA EXCLUSIVA]                  ¿El usuario es ADMIN?
          /            \                           /          \
  (Legajo Inválido) (Legajo Válido)              (NO)         (SÍ)
        /                \                       /              \
  [Reintento]    [ESPERANDO_FECHA_INICIO]     Denegado  [Procesar Planilla]
                       /          \                      |
               (Fecha Inválida) (Fecha Válida)      Enviar Alertas
                     /              \                    |
               [Reintento]    [ESPERANDO_FECHA_FIN]    (FIN)
                               [COMPUERTA EXCLUSIVA]
                                /          \
                        (Fecha Inválida) (Fecha Válida)
                              /              \
                        [Reintento]            \
                                                [COMPUERTA EXCLUSIVA]
                                                 (¿Hay superposición?)
                                                       /         \
                                                     (SÍ)        (NO)
                                                      /             \
                                              [Registrar como]   [Registrar como]
                                                 PENDIENTE           APROBADO
                                                     /                 /
                                                   /                /
                                            [ REVISION MANUAL /FIN DE CONVERSACIÓN ]
                                               

## 🤖 Comandos del Bot

El bot cuenta con comandos específicos dependiendo del rol del usuario (Empleado o RRHH):

**Comandos para Empleados:**
*`/vacaciones` : Inicia el flujo conversacional para solicitar una nueva solicitud de vacaciones.
Pide legajo, fecha de inicio y fecha de fin.

*`/cancel` : Botón de emergencia o cancelación.
Interrumpe cualquier proceso para darle posibilidad de equivocarse al usuario.

**Comandos para Recursos Humanos:**
*`/rrhh_notificar` : Comando de uso exclusivo para administradores.
Escanea la base de datos en busca de solicitudes resueltas manualmente (Aprobado/Rechazado) que aún no hayan sido notificadas (Columna J = "NO") y envía el veredicto final al Telegram del empleado correspondiente, luego de ejecutar el comando.

Para poder usar el sistema como un empleado de RRHH y probar este comando se puede agregar en la linea 27 del código, agregar una "," a la lista ingresando su ID de telegram.
Se puede obtener la ID de telegram para agregar al código escribiendole al bot @userinfobot, copiar el código que aparece y pegarlo seguido de una coma en esa lista (ADMINS_RRHH).
