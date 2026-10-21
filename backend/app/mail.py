"""Outgoing email. Only sign-in codes for now.

With SMTP settings (any provider: Gmail with an app password, Brevo, Resend, SES…) mail is
sent for real. Without them, which config validation allows only for local development, the
message is written to the log and the API shows the code on screen instead.
"""

import logging
import smtplib
import ssl
from email.message import EmailMessage
from typing import Annotated, Protocol

from fastapi import Depends

from app.config import get_settings

logger = logging.getLogger(__name__)


class Mailer(Protocol):
    def send(self, to: str, subject: str, body: str) -> None: ...


class SmtpMailer:
    def send(self, to: str, subject: str, body: str) -> None:
        settings = get_settings()
        message = EmailMessage()
        message["From"] = settings.smtp_from
        message["To"] = to
        message["Subject"] = subject
        message.set_content(body)
        context = ssl.create_default_context()
        password = settings.smtp_password.get_secret_value() if settings.smtp_password else None
        if settings.smtp_port == 465:
            server = smtplib.SMTP_SSL(settings.smtp_host, 465, context=context, timeout=15)
        else:
            server = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15)
            server.starttls(context=context)
        with server:
            if settings.smtp_username and password:
                server.login(settings.smtp_username, password)
            server.send_message(message)


class LogMailer:
    """Local development without SMTP: the message goes to the backend log."""

    def send(self, to: str, subject: str, body: str) -> None:
        logger.warning("dev mail (SMTP not configured) to=%s subject=%s\n%s", to, subject, body)


def get_mailer() -> Mailer:
    return SmtpMailer() if get_settings().smtp_host else LogMailer()


MailerDep = Annotated[Mailer, Depends(get_mailer)]


def send_sign_in_code(mailer: Mailer, to: str, code: str) -> None:
    mailer.send(
        to,
        f"{code} is your NoteMind sign-in code",
        f"Your NoteMind sign-in code is {code}\n\n"
        "It expires in 10 minutes. If you didn't try to sign in, someone has your password: "
        "change it, and don't share this code with anyone.\n",
    )
