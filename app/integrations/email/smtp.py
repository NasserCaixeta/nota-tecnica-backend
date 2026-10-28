import asyncio
import smtplib
from email.message import EmailMessage

from app.core.config import get_settings


class EmailDeliveryUnavailable(RuntimeError):
    pass


class SMTPEmailSender:
    async def send(self, *, recipient: str, subject: str, text: str, message_id: str):
        settings = get_settings()
        if not settings.smtp_enabled or (
            settings.smtp_capture_only
            and settings.smtp_host not in {"localhost", "127.0.0.1", "::1", "mailpit"}
        ):
            raise EmailDeliveryUnavailable()
        message = EmailMessage()
        message["From"] = settings.smtp_from_address
        message["To"] = recipient
        message["Subject"] = subject
        message["Message-ID"] = f"<{message_id}>"
        message.set_content(text)

        def send():
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as client:
                if settings.smtp_starttls:
                    client.starttls()
                if settings.smtp_username:
                    client.login(settings.smtp_username, settings.smtp_password.get_secret_value())
                client.send_message(message)

        try:
            await asyncio.to_thread(send)
        except (OSError, smtplib.SMTPException, ValueError):
            raise EmailDeliveryUnavailable() from None
