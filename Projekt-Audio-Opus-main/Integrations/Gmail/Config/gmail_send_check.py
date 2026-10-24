"""Ręczny skrypt diagnostyczny Gmail API.

Uruchamiany osobno (`python -m Integrations.Gmail.Config.gmail_send_check`),
NIE jest testem automatycznym - wymaga pliku credentials.json i interakcji
użytkownika przy logowaniu OAuth. Cała logika jest w main(), żeby sam import
modułu (np. przez pytest) niczego nie odpalał.
"""

from Integrations.Gmail.Config.gmail_auth import get_gmail_service


def main():
    service = get_gmail_service()

    result = service.users().messages().list(
        userId="me",
        maxResults=5
    ).execute()

    messages = result.get("messages", [])

    print("Liczba wiadomości:", len(messages))

    for message in messages:
        data = service.users().messages().get(
            userId="me",
            id=message["id"],
            format="metadata"
        ).execute()

        headers = data["payload"]["headers"]

        subject = next(
            (
                header["value"]
                for header in headers
                if header["name"] == "Subject"
            ),
            "(brak tematu)"
        )

        sender = next(
            (
                header["value"]
                for header in headers
                if header["name"] == "From"
            ),
            "(nieznany)"
        )

        print(sender, "->", subject)


if __name__ == "__main__":
    main()
