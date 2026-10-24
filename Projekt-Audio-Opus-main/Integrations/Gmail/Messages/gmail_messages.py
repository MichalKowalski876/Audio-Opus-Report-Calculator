import base64
from email.utils import parsedate_to_datetime

from Integrations.Gmail.Config.gmail_auth import get_gmail_service


def _get_header(headers, name, default=""):
    return next(
        (
            header["value"]
            for header in headers
            if header["name"].lower() == name.lower()
        ),
        default
    )


def _decode_body(data):
    if not data:
        return ""

    try:
        decoded = base64.urlsafe_b64decode(data)
        return decoded.decode("utf-8", errors="replace")
    except Exception:
        return ""


def _find_text_part(payload):
    mime_type = payload.get("mimeType", "")
    body = payload.get("body", {})

    if mime_type == "text/plain":
        return _decode_body(body.get("data"))

    parts = payload.get("parts", [])

    for part in parts:
        if part.get("mimeType") == "text/plain":
            text = _find_text_part(part)

            if text:
                return text

    for part in parts:
        text = _find_text_part(part)

        if text:
            return text

    return ""


def _find_attachments(payload):
    attachments = []

    def walk(part):
        filename = part.get("filename", "")
        mime_type = part.get("mimeType", "")
        body = part.get("body", {})

        attachment_id = body.get("attachmentId")

        if filename and attachment_id:
            attachments.append(
                {
                    "filename": filename,
                    "mime_type": mime_type,
                    "attachment_id": attachment_id,
                    "size": body.get("size", 0),
                }
            )

        for child in part.get("parts", []):
            walk(child)

    walk(payload)

    return attachments


def _format_date(value):
    if not value:
        return ""

    try:
        date = parsedate_to_datetime(value)

        if date:
            return date.astimezone().strftime("%d.%m.%Y %H:%M")

    except (TypeError, ValueError, OverflowError):
        pass

    return value


def get_messages(
        max_results=20,
        label="INBOX",
        page_token=None,
        query="",
):
    service = get_gmail_service()

    request = {
        "userId": "me",
        "maxResults": max_results,
    }

    if label:
        request["labelIds"] = [label]

    if page_token:
        request["pageToken"] = page_token

    if query:
        request["q"] = query

    result = service.users().messages().list(
        **request
    ).execute(
        num_retries=2
    )

    message_refs = result.get("messages", [])

    messages = []

    for message_ref in message_refs:
        try:
            data = service.users().messages().get(
                userId="me",
                id=message_ref["id"],
                format="full",
            ).execute(
                num_retries=2
            )
        except Exception:
            # Pojedyncza uszkodzona/niedostępna wiadomość nie powinna
            # przerwać ładowania całej strony poczty.
            continue

        payload = data.get("payload", {})
        headers = payload.get("headers", [])

        sender = _get_header(
            headers,
            "From",
            "(nieznany nadawca)"
        )

        recipient = _get_header(
            headers,
            "To",
            "(brak odbiorcy)"
        )

        subject = _get_header(
            headers,
            "Subject",
            "(brak tematu)"
        )

        date = _format_date(
            _get_header(headers, "Date")
        )

        messages.append(
            {
                "id": data.get("id"),
                "thread_id": data.get("threadId"),
                "unread": "UNREAD" in data.get("labelIds", []),
                "timestamp": int(data.get("internalDate", 0)),
                "sender": sender,
                "recipient": recipient,
                "subject": subject,
                "date": date,
                "preview": data.get("snippet", ""),
                "body": None,
                "attachments": _find_attachments(payload),
                "loaded": False,
            }
        )

    return {
        "messages": messages,
        "next_page_token": result.get("nextPageToken"),
    }


def get_message(message_id):
    service = get_gmail_service()

    data = service.users().messages().get(
        userId="me",
        id=message_id,
        format="full"
    ).execute(
        num_retries=2
    )

    payload = data.get("payload", {})
    headers = payload.get("headers", [])

    sender = _get_header(
        headers,
        "From",
        "(nieznany nadawca)"
    )

    recipient = _get_header(
        headers,
        "To",
        "(brak odbiorcy)"
    )

    subject = _get_header(
        headers,
        "Subject",
        "(brak tematu)"
    )

    date = _format_date(
        _get_header(headers, "Date")
    )

    body = _find_text_part(payload)

    if not body:
        body = data.get("snippet", "")

    return {
        "id": data.get("id"),
        "thread_id": data.get("threadId"),
        "unread": "UNREAD" in data.get("labelIds", []),
        "timestamp": int(data.get("internalDate", 0)),
        "sender": sender,
        "recipient": recipient,
        "subject": subject,
        "date": date,
        "preview": data.get("snippet", ""),
        "body": body,
        "attachments": _find_attachments(payload),
        "loaded": True,
    }


def download_attachment(message_id, attachment_id):
    service = get_gmail_service()

    attachment = (
        service.users()
        .messages()
        .attachments()
        .get(
            userId="me",
            messageId=message_id,
            id=attachment_id
        )
        .execute(
            num_retries=2
        )
    )

    data = attachment.get("data")

    if not data:
        raise ValueError(
            "Gmail API nie zwróciło danych załącznika."
        )

    return base64.urlsafe_b64decode(data)