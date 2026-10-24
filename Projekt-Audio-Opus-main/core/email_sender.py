import os
import smtplib
import json
import logging
from pathlib import Path
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import keyring
from keyring.errors import NoKeyringError
from core.email_log import log_send
from core import paths

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

DB_DIR = Path(paths.data_path("Databases"))
SMTP_CONFIG_FILE = DB_DIR / "smtp_config.json"
MSG_CONFIG_FILE = DB_DIR / "msg_config.json"
KEYRING_SERVICE = "Audio Opus SMTP"


def load_json_config(file_path: Path, default_data: dict) -> dict:
    if file_path.exists():
        try:
            with file_path.open("r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            logging.error(f"Plik {file_path.name} jest uszkodzony (błąd JSON): {e}")
        except Exception as e:
            logging.error(f"Nieoczekiwany błąd ładowania pliku {file_path.name}: {e}")

    return default_data


def send_report_email(receiver_emails, attachment_path: str | Path,
                       custom_subject: str | None = None,
                       custom_body: str | None = None) -> dict[str, tuple[bool, str | None]]:
    if isinstance(receiver_emails, str):
        receiver_emails = [receiver_emails]
    receiver_emails = [e.strip() for e in receiver_emails if e.strip()]

    if not receiver_emails:
        logging.error("Brak odbiorców.")
        return {}

    attachment_path = Path(attachment_path)

    smtp_defaults = {
        "SMTP_SERVER": "smtp.gmail.com",
        "SMTP_PORT": 465,
        "SENDER_EMAIL": "",
        "SENDER_PASSWORD": ""
    }

    msg_defaults = {
        "EMAIL_SUBJECT": "Zbiorczy raport rozliczeniowy Audio Opus",
        "EMAIL_BODY": "Dzień dobry,\n\nW załączniku znajduje się aktualny raport rozliczeniowy wygenerowany przez system Audio Opus.",
        "EMAIL_FOOTER": ""
    }

    smtp_config = load_json_config(SMTP_CONFIG_FILE, smtp_defaults)
    msg_config = load_json_config(MSG_CONFIG_FILE, msg_defaults)

    server_host = smtp_config.get("SMTP_SERVER", "smtp.gmail.com")
    try:
        server_port = int(smtp_config.get("SMTP_PORT", 465))
    except ValueError:
        server_port = 465

    sender_email = os.getenv("SMTP_EMAIL") or smtp_config.get("SENDER_EMAIL")
    sender_password = os.getenv("SMTP_PASSWORD")
    if not sender_password:
        try:
            sender_password = keyring.get_password(
                KEYRING_SERVICE, sender_email or ""
            )
        except NoKeyringError:
            sender_password = None

    email_subject = custom_subject or msg_config.get("EMAIL_SUBJECT", msg_defaults["EMAIL_SUBJECT"])

    FOOTER_SEPARATOR = "\n--\n"

    if custom_body is not None:
        full_body_raw = custom_body

        if FOOTER_SEPARATOR in custom_body:
            main_part_raw, footer_part_raw = custom_body.split(FOOTER_SEPARATOR, 1)
        else:
            main_part_raw, footer_part_raw = custom_body, ""

        formatted_body = main_part_raw.replace('\n', '<br>')
        formatted_footer = footer_part_raw.replace('\n', '<br>')

        footer_html = f"""
                <hr style="border: none; border-top: 1px solid #cccccc; margin: 20px 0;">
                <div style="font-size: 12px; color: #666666;">{formatted_footer}</div>
        """ if footer_part_raw.strip() else ""
    else:
        email_body_raw = msg_config.get("EMAIL_BODY", msg_defaults["EMAIL_BODY"])
        email_footer_raw = msg_config.get("EMAIL_FOOTER", msg_defaults["EMAIL_FOOTER"]).strip()

        if email_footer_raw:
            full_body_raw = email_body_raw + "\n\n--\n" + email_footer_raw
        else:
            full_body_raw = email_body_raw

        formatted_body = email_body_raw.replace('\n', '<br>')
        formatted_footer = email_footer_raw.replace('\n', '<br>')

        footer_html = f"""
                <hr style="border: none; border-top: 1px solid #cccccc; margin: 20px 0;">
                <div style="font-size: 12px; color: #666666;">{formatted_footer}</div>
        """ if email_footer_raw else ""

    results: dict[str, tuple[bool, str | None]] = {}

    def _fail_all(error_msg: str) -> dict[str, tuple[bool, str | None]]:
        for email in receiver_emails:
            log_send([email], attachment_path.name, "error", error_msg)
            results[email] = (False, error_msg)
        return results

    if not sender_email or not sender_password:
        logging.error("Brak danych logowania nadawcy! Ustaw e-mail i hasło w środowisku lub configu.")
        return _fail_all("Brak danych logowania nadawcy")

    if not attachment_path.exists():
        logging.error(f"Plik załącznika {attachment_path} nie istnieje!")
        return _fail_all("Plik załącznika nie istnieje")

    try:
        with attachment_path.open("rb") as f:
            attachment_bytes = f.read()
    except Exception as e:
        error_msg = f"Błąd pakowania załącznika: {e}"
        logging.error(error_msg)
        return _fail_all(error_msg)

    html_content = f"""
    <html>
        <body style="font-family: Arial, sans-serif; font-size: 14px;">
            {formatted_body}
            {footer_html}
        </body>
    </html>
    """

    try:
        logging.info(f"Łączenie z serwerem SMTP ({server_host}:{server_port})...")
        server = smtplib.SMTP_SSL(server_host, server_port)
        server.login(sender_email, sender_password)
    except smtplib.SMTPAuthenticationError:
        logging.error(
            "Błąd uwierzytelniania: nieprawidłowy e-mail lub hasło. Sprawdź, czy nie potrzebujesz 'Hasła aplikacji' (App Password).")
        return _fail_all("Błąd uwierzytelniania SMTP")
    except Exception as e:
        logging.error(f"Błąd połączenia z serwerem SMTP: {e}")
        return _fail_all(str(e))

    try:
        for receiver_email in receiver_emails:
            msg = MIMEMultipart("mixed")
            msg["From"] = sender_email
            msg["To"] = receiver_email
            msg["Subject"] = email_subject

            body_part = MIMEMultipart("alternative")
            body_part.attach(MIMEText(full_body_raw, "plain", "utf-8"))
            body_part.attach(MIMEText(html_content, "html", "utf-8"))
            msg.attach(body_part)

            attachment = MIMEApplication(attachment_bytes, _subtype="octet-stream")
            attachment.add_header("Content-Disposition", "attachment", filename=attachment_path.name)
            msg.attach(attachment)

            try:
                server.sendmail(sender_email, [receiver_email], msg.as_string())
                logging.info(f"E-mail został pomyślnie wysłany na: {receiver_email}.")
                log_send([receiver_email], attachment_path.name, "success")
                results[receiver_email] = (True, None)
            except Exception as e:
                logging.error(f"Błąd wysyłania e-maila do {receiver_email}: {e}")
                log_send([receiver_email], attachment_path.name, "error", str(e))
                results[receiver_email] = (False, str(e))
    finally:
        try:
            server.quit()
        except Exception:
            pass

    return results
