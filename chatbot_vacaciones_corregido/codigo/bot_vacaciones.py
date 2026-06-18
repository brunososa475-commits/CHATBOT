import logging
import gspread
import os
from datetime import datetime
from oauth2client.service_account import ServiceAccountCredentials
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ConversationHandler,
    ContextTypes
)

# ─── CONFIGURACIÓN ────────────────────────────────────────────────────────────

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# IDs de Telegram autorizados para usar /rrhh_notificar
ADMINS_RRHH = [7535226391]  # Agregar IDs del equipo de RRHH

# Estados de la máquina de estados (FSM)
ESPERANDO_LEGAJO, ESPERANDO_FECHA_INICIO, ESPERANDO_FECHA_FIN = range(3)


# ─── CONEXIÓN A GOOGLE SHEETS ─────────────────────────────────────────────────

def conectar_sheets():
    """Establece la conexión usando credenciales relativas al script."""
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    ruta_json = os.path.join(os.path.dirname(__file__), "..", "credenciales.json")
    creds = ServiceAccountCredentials.from_json_keyfile_name(ruta_json, scope)
    return gspread.authorize(creds).open("BD_Gestion_Vacaciones")


# ─── FLUJO DEL EMPLEADO ───────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "👋 ¡Bienvenido al Sistema de Gestión de Vacaciones!\n\n"
        "👤 Ingresá tu número de *Legajo* para comenzar.\n\n"
        "En cualquier momento podés escribir /cancel para cancelar el proceso."
    )
    return ESPERANDO_LEGAJO


async def procesar_legajo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    BPMN — Bot: ¿Legajo válido?
    Busca el legajo en la hoja 'empleados'.
    - No encontrado → mensaje de error, vuelve a pedir legajo.
    - Encontrado     → guarda datos del empleado, pide fecha de inicio.
    """
    legajo_ingresado = update.message.text.strip()

    try:
        doc = conectar_sheets()
        hoja_empleados = doc.worksheet("empleados")
        celda = hoja_empleados.find(legajo_ingresado, in_column=1)

        if celda:
            fila = hoja_empleados.row_values(celda.row)
            context.user_data['legajo']        = legajo_ingresado
            context.user_data['nombre']        = fila[1]       # Columna B: nombre_apellido
            context.user_data['disponibles']   = int(fila[2])  # Columna C: dias_disponibles
            context.user_data['sector']        = fila[4]       # Columna E: area
            context.user_data['fila_empleado'] = celda.row

            await update.message.reply_text(
                f"✅ Empleado: *{context.user_data['nombre']}* ({context.user_data['sector']})\n"
                f"📅 Días disponibles: *{context.user_data['disponibles']} días*\n\n"
                "👉 Ingresá la *Fecha de Inicio* de tus vacaciones (DD/MM/AAAA):"
            )
            return ESPERANDO_FECHA_INICIO

        else:
            # BPMN — Bot: ¿Legajo válido? → no → vuelve a pedir
            await update.message.reply_text(
                "❌ El legajo ingresado no existe. Intentá de nuevo:"
                "_/cancel para salir._"
            )
            return ESPERANDO_LEGAJO

    except Exception as e:
        logging.error(f"Error al buscar legajo: {e}")
        await update.message.reply_text(
            "⚠️ Hubo un problema al conectar con la base de datos. Intentá más tarde."
        )
        return ConversationHandler.END


async def procesar_fecha_inicio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    BPMN — Bot: validar fechas correctas (parte 1)
    Valida formato y que la fecha no sea pasada.
    - Inválida → mensaje de corrección, vuelve a pedir.
    - Válida    → guarda y pide fecha de fin.
    """
    fecha_str = update.message.text.strip()

    try:
        fecha_inicio = datetime.strptime(fecha_str, "%d/%m/%Y").date()
    except ValueError:
        # BPMN — Generar mensaje: Error/corrección
        await update.message.reply_text(
            "❌ Formato inválido. Usá DD/MM/AAAA (ejemplo: 15/07/2026):"
            "_/cancel para salir._"
        )
        return ESPERANDO_FECHA_INICIO

    if fecha_inicio < datetime.now().date():
        await update.message.reply_text(
            "❌ No podés solicitar vacaciones para una fecha pasada.\n"
            "Ingresá una fecha de hoy en adelante:"
        )
        return ESPERANDO_FECHA_INICIO

    context.user_data['fecha_inicio'] = fecha_inicio
    await update.message.reply_text(
        "👉 Ahora ingresá la *Fecha de Fin* de tus vacaciones (DD/MM/AAAA):"
    )
    return ESPERANDO_FECHA_FIN


async def procesar_fecha_fin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    BPMN — Bot: validar fechas correctas (parte 2) + cruzar con BD de vacaciones.

    Validaciones en orden:
      1. Formato de fecha
      2. Fecha fin no anterior a inicio
      3. Días solicitados no superan los disponibles
      4. Solapamiento propio (fechas ya pedidas por el mismo empleado)
         → forma parte de 'validar fechas' según el BPMN
      5. Superposición de sector con solicitudes Aprobadas de otros
         → BPMN: 'Cruzar fechas con BD de vacaciones'

    Resultado:
      - Sin superposición de sector → Pre-Aprobar (Aprobado automático)
      - Con superposición de sector → Pendiente + notificar derivación a RRHH
    """
    fecha_str = update.message.text.strip()

    # ── 1. Parsear fecha del usuario (try propio, no mezcla con lógica de BD) ──
    try:
        fecha_fin = datetime.strptime(fecha_str, "%d/%m/%Y").date()
    except ValueError:
        # BPMN — Generar mensaje: Error/corrección
        await update.message.reply_text(
            "❌ Formato inválido. Usá DD/MM/AAAA (ejemplo: 30/07/2026):"
        )
        return ESPERANDO_FECHA_FIN

    fecha_inicio = context.user_data['fecha_inicio']

    # ── 2. Fecha fin no puede ser anterior a inicio ───────────────────────────
    if fecha_fin < fecha_inicio:
        await update.message.reply_text(
            "❌ La fecha de fin no puede ser anterior a la de inicio. Ingresala de nuevo:"
        )
        return ESPERANDO_FECHA_FIN

    dias_solicitados = (fecha_fin - fecha_inicio).days + 1
    disponibles      = context.user_data['disponibles']

    # ── 3. Días disponibles suficientes ──────────────────────────────────────
    if dias_solicitados > disponibles:
        await update.message.reply_text(
            f"❌ Solicitaste *{dias_solicitados} días* pero solo tenés *{disponibles}* disponibles.\n"
            "Ingresá una nueva *Fecha de Inicio*:"
        )
        return ESPERANDO_FECHA_INICIO

    # ── Lógica de BD (try separado para no confundir errores) ─────────────────
    try:
        doc              = conectar_sheets()
        hoja_sol         = doc.worksheet("solicitud_de_vacaciones")
        todas_filas      = hoja_sol.get_all_values()
        hoja_empleados   = doc.worksheet("empleados")
        datos_empleados  = hoja_empleados.get_all_records()
        legajo_actual    = str(context.user_data['legajo'])
        sector_empleado  = context.user_data['sector']

        # ── 4. Solapamiento propio (BPMN: validar fechas) ─────────────────────
        # El mismo empleado no puede pedir fechas que pisen solicitudes propias
        # activas (Aprobadas o Pendientes).
        for fila in todas_filas[1:]:
            if len(fila) < 6:
                continue
            if str(fila[1]) != legajo_actual:
                continue
            if fila[5] not in ('Aprobado', 'Pendiente'):
                continue
            try:
                fi_exist = datetime.strptime(fila[2], "%Y-%m-%d").date()
                ff_exist = datetime.strptime(fila[3], "%Y-%m-%d").date()
                if (fecha_inicio <= ff_exist) and (fecha_fin >= fi_exist):
                    await update.message.reply_text(
                        "❌ Esas fechas se solapan con una solicitud tuya ya existente "
                        "(Aprobada o Pendiente). Ingresá un período diferente:"
                    )
                    return ESPERANDO_FECHA_INICIO
            except ValueError:
                continue

        # ── 5. Superposición de sector (BPMN: Cruzar fechas con BD) ───────────
        # Si hay Aprobadas de otro empleado del mismo sector en esas fechas
        # → derivar a revisión manual de RRHH.
        mapa_sectores = {
            str(emp['id_empleado']): emp['area']
            for emp in datos_empleados
            if 'id_empleado' in emp
        }

        superposicion_sector = False
        for fila in todas_filas[1:]:
            if len(fila) < 6:
                continue
            id_emp_sol = str(fila[1])
            if id_emp_sol == legajo_actual:
                continue  # no comparar consigo mismo
            if fila[5] != 'Aprobado':
                continue
            if mapa_sectores.get(id_emp_sol) != sector_empleado:
                continue
            try:
                fi_sol = datetime.strptime(fila[2], "%Y-%m-%d").date()
                ff_sol = datetime.strptime(fila[3], "%Y-%m-%d").date()
                if (fecha_inicio <= ff_sol) and (fecha_fin >= fi_sol):
                    superposicion_sector = True
                    break
            except ValueError:
                continue

        # ── Determinar estado final ────────────────────────────────────────────
        fecha_hoy = str(datetime.now().date())
        chat_id   = update.message.chat_id

        if superposicion_sector:
            # BPMN — Bot: hay superposición → Pendiente + notificar derivación
            estado   = "Pendiente"
            motivo   = (
                f"Superposición detectada en sector '{sector_empleado}'. "
                "Requiere validación manual de RRHH."
            )
            fue_notificado = "NO"  # RRHH lo resolverá y disparará la notificación

            mensaje_usuario = (
                f"⚠️ *Atención:* tus fechas se superponen con un compañero del sector "
                f"*{sector_empleado}*.\n\n"
                f"Tu solicitud de *{dias_solicitados} días* quedó como *PENDIENTE*.\n"
                "El equipo de RRHH evaluará el caso y te notificará."
            )

        else:
            # BPMN — Bot: sin superposición → Pre-Aprobar (Aprobado automático)
            estado   = "Aprobado"
            motivo   = "Aprobado automáticamente por el Bot."
            fue_notificado = "SI"  # se notifica al instante en este mismo mensaje

            # Descontar días del empleado
            hoja_empleados.update_cell(
                context.user_data['fila_empleado'], 3, disponibles - dias_solicitados
            )

            mensaje_usuario = (
                f"🎉 Tu solicitud de *{dias_solicitados} días* fue *APROBADA AUTOMÁTICAMENTE*.\n\n"
                f"📅 Período: {fecha_inicio.strftime('%d/%m/%Y')} al {fecha_fin.strftime('%d/%m/%Y')}.\n"
                "Los días ya fueron descontados de tu legajo."
            )

        # ── Generar ID autoincremental ─────────────────────────────────────────
        total_filas = len(todas_filas)
        if total_filas <= 1:
            id_nuevo = 101
        else:
            try:
                id_nuevo = int(todas_filas[-1][0]) + 1
            except ValueError:
                id_nuevo = 100 + total_filas

        # ── Insertar en hoja solicitud_de_vacaciones (10 columnas) ────────────
        hoja_sol.append_row([
            id_nuevo,                          # A: id_solicitud
            legajo_actual,                     # B: id_empleado
            str(fecha_inicio),                 # C: fecha_inicio
            str(fecha_fin),                    # D: fecha_fin
            dias_solicitados,                  # E: dias_solicitados
            estado,                            # F: estado_tramite
            fecha_hoy,                         # G: fecha_solicitud
            motivo,                            # H: observaciones
            chat_id,                           # I: chat_id_empleado
            fue_notificado                     # J: notificado (SI/NO)
        ])

        await update.message.reply_text(mensaje_usuario, parse_mode="Markdown")
        return ConversationHandler.END

    except Exception as e:
        logging.error(f"Error al procesar solicitud: {e}")
        await update.message.reply_text(
            "⚠️ Hubo un problema al conectar con la base de datos. Intentá más tarde."
        )
        return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancela el proceso en cualquier momento con /cancel."""
    await update.message.reply_text(
        "🚫 Proceso cancelado. Podés volver a empezar con /vacaciones."
    )
    return ConversationHandler.END


# ─── FLUJO DE RRHH ────────────────────────────────────────────────────────────

async def rrhh_notificar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    BPMN — RRHH: detecta solicitudes Pendientes ya resueltas (Aprobado/Rechazado)
    con la bandera 'notificado = NO' y envía el resultado al empleado por Telegram.

    Uso: /rrhh_notificar
    Acceso restringido a los IDs en ADMINS_RRHH.

    Flujo esperado:
      1. RRHH cambia manualmente el estado en Sheets (Pendiente → Aprobado/Rechazado)
         y actualiza días si aprueba.
      2. RRHH ejecuta /rrhh_notificar → el bot envía el resultado a cada empleado
         y marca la columna J como 'SI' para no repetir.
    """
    if update.message.chat_id not in ADMINS_RRHH:
        await update.message.reply_text(
            "⛔ Acceso denegado. Comando exclusivo para Recursos Humanos."
        )
        return

    await update.message.reply_text(
        "🔍 Revisando solicitudes resueltas pendientes de notificación..."
    )

    try:
        doc      = conectar_sheets()
        hoja_sol = doc.worksheet("solicitud_de_vacaciones")
        todas    = hoja_sol.get_all_values()
        enviados = 0

        for i, fila in enumerate(todas[1:], start=2):
            # Necesita 10 columnas, estado final resuelto y bandera NO
            if len(fila) < 10:
                continue
            if fila[5] not in ('Aprobado', 'Rechazado'):
                continue
            if fila[9] != 'NO':
                continue

            chat_id_destino = fila[8]
            estado_final    = fila[5]
            motivo          = fila[7]
            id_solicitud    = fila[0]

            mensaje = (
                f"🔔 *Aviso de RRHH*\n\n"
                f"Tu solicitud N° {id_solicitud} fue resuelta.\n"
                f"Estado: *{estado_final}*\n"
                f"Observaciones: {motivo}"
            )

            try:
                await context.bot.send_message(
                    chat_id=chat_id_destino,
                    text=mensaje,
                    parse_mode='Markdown'
                )
                hoja_sol.update_cell(i, 10, "SI")  # marcar como notificado
                enviados += 1
            except Exception as e:
                logging.error(f"Error al notificar chat {chat_id_destino}: {e}")

        if enviados > 0:
            await update.message.reply_text(
                f"✅ Se enviaron *{enviados}* notificaciones exitosamente.",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(
                "✅ No hay solicitudes resueltas pendientes de notificar."
            )

    except Exception as e:
        logging.error(f"Error en rrhh_notificar: {e}")
        await update.message.reply_text(f"⚠️ Error al acceder a la planilla: {e}")


# ─── INICIALIZACIÓN DEL BOT ───────────────────────────────────────────────────

if __name__ == '__main__':
    TOKEN = "8807520548:AAGVqkL7OOAuKs1suGhs2ZK3KDmKUMmTy3Q"

    app = Application.builder().token(TOKEN).build()

    # Flujo del empleado (ConversationHandler)
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('vacaciones', start)],
        states={
            ESPERANDO_LEGAJO:      [MessageHandler(filters.TEXT & ~filters.COMMAND, procesar_legajo)],
            ESPERANDO_FECHA_INICIO:[MessageHandler(filters.TEXT & ~filters.COMMAND, procesar_fecha_inicio)],
            ESPERANDO_FECHA_FIN:   [MessageHandler(filters.TEXT & ~filters.COMMAND, procesar_fecha_fin)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    app.add_handler(conv_handler)

    # Comando exclusivo de RRHH
    app.add_handler(CommandHandler('rrhh_notificar', rrhh_notificar))

    app.run_polling()