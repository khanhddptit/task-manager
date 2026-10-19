import os
import smtplib
import ssl
from urllib.parse import urlsplit


def configured_public_url():
    raw_url = os.environ.get("PUBLIC_APP_URL", "").strip()
    if not raw_url:
        return None
    parsed = urlsplit(raw_url)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.netloc
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        return None
    return raw_url.rstrip("/")


def smtp_sender():
    return os.environ.get("SMTP_FROM", "").strip()


def smtp_is_configured():
    host = os.environ.get("SMTP_HOST", "").strip()
    sender = smtp_sender()
    username = os.environ.get("SMTP_USERNAME", "").strip()
    password = os.environ.get("SMTP_PASSWORD", "")
    return bool(host and sender) and bool(username) == bool(password)


def send_email(message):
    if not smtp_is_configured():
        return "not_configured"

    host = os.environ["SMTP_HOST"].strip()
    username = os.environ.get("SMTP_USERNAME", "").strip()
    password = os.environ.get("SMTP_PASSWORD", "")
    try:
        port = int(os.environ.get("SMTP_PORT", "587"))
        use_ssl = os.environ.get("SMTP_USE_SSL", "false").lower() in {"1", "true", "yes"}
        use_tls = os.environ.get("SMTP_USE_TLS", "true").lower() in {"1", "true", "yes"}
        client_class = smtplib.SMTP_SSL if use_ssl else smtplib.SMTP
        options = {"timeout": 10}
        if use_ssl:
            options["context"] = ssl.create_default_context()
        with client_class(host, port, **options) as smtp:
            if not use_ssl and use_tls:
                smtp.starttls(context=ssl.create_default_context())
            if username:
                smtp.login(username, password)
            smtp.send_message(message)
    except (OSError, smtplib.SMTPException, ValueError):
        return "failed"
    return "sent"
