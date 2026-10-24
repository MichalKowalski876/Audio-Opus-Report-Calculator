import json
import urllib.error
import urllib.request

from core import paths

OLLAMA_URL = "http://127.0.0.1:11434"
DEFAULT_MODEL = "qwen2.5:1.5b"

BASE_SYSTEM_PROMPT = """Jesteś asystentem aplikacji Audio Opus.
Odpowiadasz po polsku, krótko i konkretnie. Pomagasz obsługiwać aplikację.
Nie wymyślaj funkcji, których nie ma w dokumentacji. Jeśli nie znasz odpowiedzi,
powiedz to wprost i wskaż zakładkę Pomoc.
"""


def _load_guide():
    guide_path = paths.resource_path("docs", "ASSISTANT_GUIDE.md")
    try:
        with open(guide_path, "r", encoding="utf-8") as guide_file:
            return guide_file.read()
    except OSError:
        return "Dokumentacja aplikacji nie jest dostępna. Odpowiadaj ostrożnie."


SYSTEM_PROMPT = f"{BASE_SYSTEM_PROMPT}\n\nBAZA WIEDZY:\n{_load_guide()}"


def _request(path, payload=None, timeout=10):
    url = f"{OLLAMA_URL}{path}"
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST" if data is not None else "GET",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def is_available(timeout=1):
    try:
        _request("/api/tags", timeout=timeout)
        return True
    except (OSError, urllib.error.URLError, json.JSONDecodeError):
        return False


def installed_models(timeout=3):
    result = _request("/api/tags", timeout=timeout)
    return {
        str(model.get("name") or model.get("model"))
        for model in result.get("models", [])
        if model.get("name") or model.get("model")
    }


def ask_stream(question, model=DEFAULT_MODEL, timeout=120):
    payload = {
        "model": model,
        "stream": True,
        "options": {"num_predict": 256},
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": question.strip()},
        ],
    }
    request = urllib.request.Request(
        f"{OLLAMA_URL}/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        for line in response:
            if not line.strip():
                continue
            chunk = json.loads(line.decode("utf-8"))
            content = chunk.get("message", {}).get("content")
            if content:
                yield str(content)


def ask(question, model=DEFAULT_MODEL, timeout=120):
    return "".join(ask_stream(question, model=model, timeout=timeout)).strip()
