# Chatbot – Gestión de Vacaciones

Chatbot web en Python/Flask que sigue el flujo BPMN de solicitud de vacaciones.
Lee y escribe directamente en un único archivo Excel con dos hojas.

## Estructura

```
chatbot_vacaciones/
├── app.py                              ← Servidor Flask + lógica del bot
├── templates/
│   └── index.html                      ← Interfaz web del chat
├── data/
│   └── base_de_datos_vacaciones.xlsx   ← Hoja "empleados" + hoja "solicitud_de_vacaciones"
└── README.md
```

## Requisitos

```bash
pip install flask openpyxl
```

## Cómo correr

```bash
python app.py
```

Abrí el navegador en: **http://localhost:5000**

## Hojas del Excel

### empleados
| Campo | Descripción |
|---|---|
| id_empleado | Legajo único del empleado |
| nombre_apellido | Nombre completo |
| dias_disponibles | Días de vacaciones disponibles |
| email | Correo institucional |
| area | Sector de la organización |
| fecha_ingreso | Fecha de ingreso |

### solicitud_de_vacaciones
| Campo | Descripción |
|---|---|
| id_solicitud | ID único (se genera automáticamente) |
| id_empleado | Legajo del solicitante |
| fecha_inicio | Inicio de vacaciones |
| fecha_fin | Fin de vacaciones |
| estado_tramite | Pendiente / Aprobado / Rechazado |
| fecha_solicitud | Fecha en que se realizó la solicitud |
