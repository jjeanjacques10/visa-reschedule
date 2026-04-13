"""
Telegram update handler for user onboarding.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

import boto3
import urllib3
from botocore.exceptions import ClientError

from app.config import config, load_config
from app.database.dynamodb_client import DynamoDBClient
from app.database.models import User

load_config()

logger = logging.getLogger(__name__)

try:
    BOT_TOKEN = config.telegram_bot_token
except RuntimeError:
    BOT_TOKEN = ""
TELEGRAM_API_BASE = f"https://api.telegram.org/bot{BOT_TOKEN}"
REG_DATA_KEY = "registration"
TELEGRAM_DATE_FORMAT = "%d/%m/%Y"

STEP_EMAIL = "email"
STEP_PASSWORD = "password"
STEP_VISA_TYPE = "visa_type"
STEP_APPOINTMENT_DATE = "appointment_date"
STEP_PREFERRED_DATES = "preferred_dates"
STEP_CONFIRM = "confirm"

_http = urllib3.PoolManager()
_db_client: DynamoDBClient | None = None
_sqs_client = None
_sessions: dict[str, dict[str, Any]] = {}


def _build_help_message() -> str:
    return (
        "🤖 <b>Comandos disponíveis</b>\n\n"
        "• /register - Iniciar novo cadastro\n"
        "• /status - Ver status do monitoramento\n"
        "• /cancel - Cancelar notificações\n"
        "• /help - Mostrar esta ajuda"
    )


def _get_db_client() -> DynamoDBClient:
    global _db_client
    if _db_client is None:
        _db_client = DynamoDBClient()
    return _db_client


def _get_sqs_client():
    global _sqs_client
    if _sqs_client is None:
        endpoint_url = None
        try:
            queue_url = config.appointment_queue_url
            parsed = urlparse(queue_url)
            if parsed.scheme and parsed.netloc:
                endpoint_url = f"{parsed.scheme}://{parsed.netloc}"
        except RuntimeError:
            endpoint_url = None

        _sqs_client = boto3.client(
            "sqs",
            region_name=config.aws_region,
            endpoint_url=endpoint_url,
        )
    return _sqs_client


def _send_sqs_registration_trigger(user: User) -> bool:
    try:
        queue_url = config.appointment_queue_url
    except RuntimeError as exc:
        logger.warning("SQS trigger skipped: %s", exc)
        return False

    try:
        payload = user.to_safe_dict()
        payload["notify_on_complete"] = True
        _get_sqs_client().send_message(
            QueueUrl=queue_url,
            MessageBody=json.dumps(payload),
        )
        logger.info("Immediate check queued for user_id=%s", user.user_id)
        return True
    except ClientError:
        logger.exception("Failed to enqueue immediate check for user_id=%s", user.user_id)
        return False


def telegram_api(method: str, payload: dict) -> dict:
    """Call Telegram Bot HTTP API."""
    if not BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not configured.")

    url = f"{TELEGRAM_API_BASE}/{method}"
    response = _http.request("POST", url, fields=payload, timeout=30)
    data = json.loads(response.data.decode("utf-8"))
    if not data.get("ok"):
        raise RuntimeError(f"Telegram API error on {method}: {data}")
    return data


def _send_message(chat_id: str, text: str, parse_mode: str = "HTML") -> None:
    telegram_api(
        "sendMessage",
        {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
        },
    )


def _validate_date(value: str) -> bool:
    try:
        datetime.strptime(value, TELEGRAM_DATE_FORMAT)
        return True
    except ValueError:
        return False


def _new_session() -> dict[str, Any]:
    return {REG_DATA_KEY: {}, "step": STEP_EMAIL}


def _build_summary(data: dict[str, Any]) -> str:
    preferred = data.get("preferred_dates") or []
    return (
        "📋 <b>Resumo do cadastro:</b>\n"
        f"E-mail: {data['email']}\n"
        f"Tipo de visto: {data['visa_type']}\n"
        f"Agendamento atual: {data['appointment_date']}\n"
        f"Datas preferidas: {', '.join(preferred) if preferred else 'Nenhuma'}\n\n"
        "Confirmar cadastro? Responda <b>Sim</b> ou <b>Não</b>."
    )


def _handle_status(chat_id: str, telegram_id: str) -> None:
    db = _get_db_client()
    user = db.get_user_by_telegram_id(telegram_id)
    if user is None:
        _send_message(chat_id, "Nenhum cadastro encontrado. Use /start para se registrar.")
        return
    _send_message(
        chat_id,
        (
            "📊 <b>Seu status:</b>\n"
            f"Tipo de visto: {user.visa_type}\n"
            f"Agendamento atual: {user.appointment_date}\n"
            f"Status: {user.status}\n"
            f"Notificações enviadas: {user.notification_count}\n"
            f"Última notificação: {user.last_notified_date or 'Nunca'}"
        ),
    )


def _handle_cancel(chat_id: str, telegram_id: str, session_key: str) -> None:
    _sessions.pop(session_key, None)
    db = _get_db_client()
    user = db.get_user_by_telegram_id(telegram_id)
    if user is not None:
        db.update_user(user.user_id, {"status": "cancelled"})
        _send_message(chat_id, "✅ Suas notificações foram canceladas.")
        return
    _send_message(chat_id, "Cadastro cancelado. Use /start para recomeçar.")


def process_telegram_update(update: dict) -> None:
    """
    Process one Telegram update payload.
    Supports the registration onboarding flow and status/cancel commands.
    """
    message = update.get("message") or {}
    text = (message.get("text") or "").strip()
    if not message or not text:
        return

    chat_id = str(message["chat"]["id"])
    user = message.get("from") or {}
    telegram_id = str(user.get("id", chat_id))
    session_key = f"{chat_id}:{telegram_id}"

    if text.lower() == "/help":
        _send_message(chat_id, _build_help_message())
        return

    if text.lower() == "/status":
        _handle_status(chat_id, telegram_id)
        return

    if text.lower() == "/cancel":
        _handle_cancel(chat_id, telegram_id, session_key)
        return

    if text.lower() == "/start":
        _send_message(
            chat_id,
            (
                "Olá! 👋 Bem-vindo ao monitor de reagendamento.\n\n"
                "Use /register para iniciar seu cadastro ou /help para ver todas as opções."
            ),
        )
        return

    if text.lower() == "/register":
        _sessions[session_key] = _new_session()
        _send_message(
            chat_id,
            (
                "Olá! 👋\n\n"
                "Vou validar sua identidade pelo seu Telegram ID e registrar seu monitoramento.\n\n"
                "Por favor, informe seu e-mail cadastrado no portal da embaixada:"
            ),
        )
        return

    session = _sessions.get(session_key)
    if not session:
        _send_message(
            chat_id,
            "Use /register para iniciar seu cadastro ou /help para ver os comandos disponíveis.",
        )
        return

    data = session[REG_DATA_KEY]
    step = session["step"]

    if step == STEP_EMAIL:
        if "@" not in text or "." not in text:
            _send_message(chat_id, "E-mail inválido. Informe um e-mail válido:")
            return
        data["email"] = text
        session["step"] = STEP_PASSWORD
        _send_message(chat_id, "Agora informe sua senha do portal AIS:")
        return

    if step == STEP_PASSWORD:
        if len(text) < 4:
            _send_message(chat_id, "Senha muito curta. Informe sua senha novamente:")
            return
        data["password"] = text
        session["step"] = STEP_VISA_TYPE
        try:
            telegram_api(
                "deleteMessage",
                {"chat_id": chat_id, "message_id": message.get("message_id")},
            )
        except Exception:  # pylint: disable=broad-except
            logger.debug("Unable to delete password message.")
        _send_message(chat_id, "Qual é o tipo de visto? (ex: B1/B2, F1)")
        return

    if step == STEP_VISA_TYPE:
        data["visa_type"] = text
        session["step"] = STEP_APPOINTMENT_DATE
        _send_message(chat_id, "Qual é a data do seu agendamento atual? (DD/MM/AAAA)")
        return

    if step == STEP_APPOINTMENT_DATE:
        if not _validate_date(text):
            _send_message(chat_id, "Data inválida. Use DD/MM/AAAA (ex: 25/12/2026):")
            return
        data["appointment_date"] = text
        session["step"] = STEP_PREFERRED_DATES
        _send_message(
            chat_id,
            (
                "Você tem datas preferidas? Envie separadas por vírgula "
                "(ex: 01/11/2026, 15/11/2026) ou /pular."
            ),
        )
        return

    if step == STEP_PREFERRED_DATES:
        preferred_dates: list[str] = []
        if text.lower() not in ("/pular", "pular"):
            candidates = [v.strip() for v in text.split(",") if v.strip()]
            if not candidates:
                _send_message(chat_id, "Use /pular ou envie ao menos uma data válida.")
                return
            if any(not _validate_date(candidate) for candidate in candidates):
                _send_message(chat_id, "Uma ou mais datas são inválidas. Use DD/MM/AAAA ou /pular.")
                return
            preferred_dates = candidates
        data["preferred_dates"] = preferred_dates or None
        session["step"] = STEP_CONFIRM
        _send_message(chat_id, _build_summary(data))
        return

    if step == STEP_CONFIRM:
        if text.lower() not in ("sim", "s", "yes", "y"):
            _sessions.pop(session_key, None)
            _send_message(chat_id, "Cadastro cancelado. Use /start para recomeçar.")
            return

        now_iso = datetime.now(tz=timezone.utc).isoformat()
        user_model = User(
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
            db = _get_db_client()
            db.create_user(user_model)
            queued = _send_sqs_registration_trigger(user_model)
            message_text = (
                "✅ Cadastro realizado com sucesso!\n\n"
                "Você já está no monitoramento e receberá notificações quando houver datas anteriores."
            )
            if not queued:
                message_text += "\n\n⚠️ Não foi possível disparar a checagem imediata, mas seu cadastro foi salvo."
            _send_message(chat_id, message_text)
            logger.info("User registered via Telegram: user_id=%s telegram_id=%s", user_model.user_id, telegram_id)
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception("Failed to register user via Telegram: %s", exc)
            _send_message(chat_id, "❌ Erro ao salvar cadastro. Tente novamente com /start.")
        finally:
            _sessions.pop(session_key, None)
