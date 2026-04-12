"""
Telegram bot for local testing of the Visa Reschedule service.
Guides users through registration via a multi-step ConversationHandler.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import uuid4

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from app.config import config, load_config

# Load .env before building the Application so the bot token is available.
load_config()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)

# Conversation states
(
    ASK_EMAIL,
    ASK_PASSWORD,
    ASK_VISA_TYPE,
    ASK_APPOINTMENT_DATE,
    ASK_PREFERRED_DATES,
    CONFIRM,
) = range(6)

# Temporary storage key in user_data
REG_DATA_KEY = "registration"


def _get_db():
    from app.database.dynamodb_client import DynamoDBClient
    return DynamoDBClient()


# ------------------------------------------------------------------
# /start
# ------------------------------------------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Begin the registration conversation."""
    user = update.effective_user
    logger.info("User started registration: telegram_id=%s", user.id)
    context.user_data[REG_DATA_KEY] = {}
    await update.message.reply_text(
        f"Olá, {user.first_name}! 👋\n\n"
        "Vou te ajudar a monitorar datas disponíveis para reagendamento do visto americano.\n\n"
        "Por favor, informe seu e-mail cadastrado no portal da embaixada:"
    )
    return ASK_EMAIL


# ------------------------------------------------------------------
# Conversation steps
# ------------------------------------------------------------------

async def ask_email(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    email = update.message.text.strip()
    if "@" not in email or "." not in email:
        await update.message.reply_text(
            "E-mail inválido. Por favor, informe um endereço de e-mail válido:"
        )
        return ASK_EMAIL

    context.user_data[REG_DATA_KEY]["email"] = email
    logger.info("Received email for telegram_id=%s", update.effective_user.id)
    await update.message.reply_text(
        "Ótimo! Agora informe sua senha do portal AIS:"
    )
    return ASK_PASSWORD


async def ask_password(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # Never log the password
    password = update.message.text.strip()
    if len(password) < 4:
        await update.message.reply_text(
            "Senha muito curta. Por favor, informe sua senha novamente:"
        )
        return ASK_PASSWORD

    context.user_data[REG_DATA_KEY]["password"] = password

    # Delete the message containing the password for security
    try:
        await update.message.delete()
    except Exception:  # pylint: disable=broad-except
        pass

    await update.message.reply_text(
        "Perfeito! Qual é o tipo de visto? (ex: B1/B2, F1, H1B, etc.)"
    )
    return ASK_VISA_TYPE


async def ask_visa_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    visa_type = update.message.text.strip()
    context.user_data[REG_DATA_KEY]["visa_type"] = visa_type
    logger.info(
        "Received visa_type=%s for telegram_id=%s",
        visa_type,
        update.effective_user.id,
    )
    await update.message.reply_text(
        "Qual é a data do seu agendamento atual? (formato: DD/MM/AAAA)"
    )
    return ASK_APPOINTMENT_DATE


async def ask_appointment_date(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    date_str = update.message.text.strip()
    try:
        datetime.strptime(date_str, "%d/%m/%Y")
    except ValueError:
        await update.message.reply_text(
            "Formato de data inválido. Use DD/MM/AAAA (ex: 25/12/2025):"
        )
        return ASK_APPOINTMENT_DATE

    context.user_data[REG_DATA_KEY]["appointment_date"] = date_str
    logger.info(
        "Received appointment_date=%s for telegram_id=%s",
        date_str,
        update.effective_user.id,
    )
    await update.message.reply_text(
        "Você tem datas preferidas? Envie-as separadas por vírgula (ex: 01/11/2025, 15/11/2025) "
        "ou envie /pular para continuar sem preferências."
    )
    return ASK_PREFERRED_DATES


async def ask_preferred_dates(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    text = update.message.text.strip()
    preferred: list = []
    if text.lower() not in ("/pular", "pular"):
        raw_dates = [d.strip() for d in text.split(",") if d.strip()]
        valid = True
        for d in raw_dates:
            try:
                datetime.strptime(d, "%d/%m/%Y")
                preferred.append(d)
            except ValueError:
                valid = False
                break
        if not valid:
            await update.message.reply_text(
                "Uma ou mais datas são inválidas. Use DD/MM/AAAA separadas por vírgula ou /pular:"
            )
            return ASK_PREFERRED_DATES

    context.user_data[REG_DATA_KEY]["preferred_dates"] = preferred or None
    data = context.user_data[REG_DATA_KEY]
    summary = (
        f"📋 <b>Resumo do cadastro:</b>\n"
        f"E-mail: {data['email']}\n"
        f"Tipo de visto: {data['visa_type']}\n"
        f"Agendamento atual: {data['appointment_date']}\n"
        f"Datas preferidas: {', '.join(preferred) if preferred else 'Nenhuma'}\n\n"
        "Confirmar cadastro? Responda <b>Sim</b> ou <b>Não</b>."
    )
    await update.message.reply_text(summary, parse_mode="HTML")
    return CONFIRM


async def confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    answer = update.message.text.strip().lower()
    if answer not in ("sim", "s", "yes", "y"):
        await update.message.reply_text(
            "Cadastro cancelado. Use /start para recomeçar."
        )
        context.user_data.pop(REG_DATA_KEY, None)
        return ConversationHandler.END

    data = context.user_data[REG_DATA_KEY]
    telegram_id = str(update.effective_user.id)
    now_iso = datetime.now(tz=timezone.utc).isoformat()

    from app.database.models import User

    user = User(
        user_id=str(uuid4()),
        telegram_id=telegram_id,
        visa_type=data["visa_type"],
        appointment_date=data["appointment_date"],
        email=data["email"],
        password=data["password"],
        created_at=now_iso,
        updated_at=now_iso,
        notification_count=0,
        status="pending",
        preferred_dates=data.get("preferred_dates"),
    )

    try:
        db = _get_db()
        db.create_user(user)
        logger.info(
            "User registered via bot: user_id=%s telegram_id=%s",
            user.user_id,
            telegram_id,
        )
        await update.message.reply_text(
            "✅ Cadastro realizado com sucesso!\n\n"
            "Você será notificado quando houver datas disponíveis anteriores ao seu agendamento. "
            "Use /status para verificar seu cadastro ou /cancel para cancelar as notificações."
        )
    except Exception as exc:  # pylint: disable=broad-except
        logger.exception("Failed to save user via bot: %s", exc)
        await update.message.reply_text(
            "❌ Erro ao salvar seu cadastro. Tente novamente com /start."
        )
    finally:
        context.user_data.pop(REG_DATA_KEY, None)

    return ConversationHandler.END


# ------------------------------------------------------------------
# /cancel and /status commands
# ------------------------------------------------------------------

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel an in-progress registration conversation or active monitoring."""
    telegram_id = str(update.effective_user.id)

    # If inside a conversation, just end it
    if context.user_data.get(REG_DATA_KEY):
        context.user_data.pop(REG_DATA_KEY, None)
        await update.message.reply_text(
            "Cadastro cancelado. Use /start para recomeçar a qualquer momento."
        )
        return ConversationHandler.END

    # Otherwise cancel active monitoring in DynamoDB
    try:
        db = _get_db()
        user = db.get_user_by_telegram_id(telegram_id)
        if user is None:
            await update.message.reply_text(
                "Nenhum cadastro encontrado para sua conta."
            )
        else:
            db.update_user(user.user_id, {"status": "cancelled"})
            logger.info(
                "User cancelled monitoring: user_id=%s telegram_id=%s",
                user.user_id,
                telegram_id,
            )
            await update.message.reply_text(
                "✅ Suas notificações foram canceladas com sucesso."
            )
    except Exception as exc:  # pylint: disable=broad-except
        logger.exception(
            "Error cancelling user monitoring for telegram_id=%s: %s",
            telegram_id,
            exc,
        )
        await update.message.reply_text(
            "❌ Erro ao cancelar. Tente novamente mais tarde."
        )
    return ConversationHandler.END


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show the user's current monitoring status."""
    telegram_id = str(update.effective_user.id)
    try:
        db = _get_db()
        user = db.get_user_by_telegram_id(telegram_id)
        if user is None:
            await update.message.reply_text(
                "Nenhum cadastro encontrado. Use /start para se registrar."
            )
            return

        last_notified = user.last_notified_date or "Nunca"
        await update.message.reply_text(
            f"📊 <b>Seu status:</b>\n"
            f"Tipo de visto: {user.visa_type}\n"
            f"Agendamento atual: {user.appointment_date}\n"
            f"Status: {user.status}\n"
            f"Notificações enviadas: {user.notification_count}\n"
            f"Última notificação: {last_notified}",
            parse_mode="HTML",
        )
    except Exception as exc:  # pylint: disable=broad-except
        logger.exception(
            "Error fetching status for telegram_id=%s: %s", telegram_id, exc
        )
        await update.message.reply_text(
            "❌ Erro ao buscar seu status. Tente novamente mais tarde."
        )


# ------------------------------------------------------------------
# Application setup
# ------------------------------------------------------------------

def build_application() -> Application:
    """Build and configure the Telegram Application."""
    try:
        bot_token = config.telegram_bot_token
    except RuntimeError as exc:
        raise RuntimeError(
            "Cannot start bot: TELEGRAM_BOT_TOKEN is not set. "
            "Add it to your .env file or set it as an environment variable."
        ) from exc

    application = Application.builder().token(bot_token).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            ASK_EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_email)],
            ASK_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_password)],
            ASK_VISA_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_visa_type)],
            ASK_APPOINTMENT_DATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, ask_appointment_date)
            ],
            ASK_PREFERRED_DATES: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, ask_preferred_dates),
                CommandHandler("pular", ask_preferred_dates),
            ],
            CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("cancel", cancel))
    application.add_handler(CommandHandler("status", status))

    return application


if __name__ == "__main__":
    logger.info("Starting Telegram bot (polling mode)")
    application = build_application()
    application.run_polling(allowed_updates=Update.ALL_TYPES)
