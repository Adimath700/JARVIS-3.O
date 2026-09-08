import base64
import mimetypes
from pathlib import Path

import requests


class GeminiVision:
    """Gemini image analysis with model discovery and automatic fallback."""

    API_ROOT = "https://generativelanguage.googleapis.com/v1beta"

    # Ordered from preferred current models to the older 2.5 model.
    FALLBACK_MODELS = (
        "gemini-3.5-flash",
        "gemini-3.1-flash-lite",
        "gemini-2.5-flash",
    )

    def __init__(self, key: str, model: str):
        self.key = key.strip()
        self.model = self._clean_model_name(model)
        self.last_model = None

    @staticmethod
    def _clean_model_name(model: str) -> str:
        value = (model or "").strip()
        if value.startswith("models/"):
            value = value[7:]
        return value

    def _headers(self) -> dict[str, str]:
        # Google currently documents x-goog-api-key header authentication.
        return {
            "x-goog-api-key": self.key,
            "Content-Type": "application/json",
        }

    def _available_models(self) -> set[str]:
        """Return models that advertise generateContent support."""
        response = requests.get(
            f"{self.API_ROOT}/models",
            headers={"x-goog-api-key": self.key},
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()

        available: set[str] = set()
        for item in payload.get("models", []):
            name = self._clean_model_name(item.get("name", ""))
            methods = item.get("supportedGenerationMethods", [])
            if name and "generateContent" in methods:
                available.add(name)
        return available

    def _candidate_models(self) -> list[str]:
        candidates: list[str] = []
        for name in (self.model, *self.FALLBACK_MODELS):
            cleaned = self._clean_model_name(name)
            if cleaned and cleaned not in candidates:
                candidates.append(cleaned)

        # If model discovery succeeds, prefer models actually advertised by the key.
        # We still keep configured/fallback candidates in the list because Google has
        # recently had cases where models.list() succeeds while generateContent is denied.
        try:
            available = self._available_models()
            if available:
                advertised = [name for name in candidates if name in available]
                others = [name for name in candidates if name not in available]
                candidates = advertised + others
        except requests.RequestException:
            pass

        return candidates

    def analyze(self, image_path: str | Path, prompt: str) -> str:
        if not self.key:
            raise RuntimeError("GOOGLE_API_KEY is not configured")

        path = Path(image_path)
        if not path.exists():
            raise FileNotFoundError(f"Screenshot not found: {path}")

        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        mime_type = mimetypes.guess_type(path.name)[0] or "image/png"

        body = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {"text": prompt},
                        {
                            "inline_data": {
                                "mime_type": mime_type,
                                "data": encoded,
                            }
                        },
                    ],
                }
            ]
        }

        failures: list[str] = []

        for model in self._candidate_models():
            url = f"{self.API_ROOT}/models/{model}:generateContent"
            try:
                response = requests.post(
                    url,
                    headers=self._headers(),
                    json=body,
                    timeout=60,
                )

                if response.ok:
                    payload = response.json()
                    candidates = payload.get("candidates") or []
                    if not candidates:
                        raise RuntimeError("Gemini returned no candidates")

                    parts = candidates[0].get("content", {}).get("parts", [])
                    text = "".join(
                        part.get("text", "")
                        for part in parts
                        if part.get("text")
                    ).strip()
                    if not text:
                        raise RuntimeError("Gemini returned an empty response")

                    self.last_model = model
                    return text

                # 404/403 commonly means this key/project cannot generate with
                # that model. Try the next current model automatically.
                if response.status_code in {400, 401, 403, 404, 429, 500, 502, 503, 504}:
                    try:
                        detail = response.json().get("error", {}).get("message", "")
                    except ValueError:
                        detail = response.text[:200]
                    failures.append(f"{model}: HTTP {response.status_code} {detail}".strip())
                    continue

                response.raise_for_status()

            except requests.RequestException as exc:
                failures.append(f"{model}: {exc}")

        detail = " | ".join(failures)
        raise RuntimeError(
            "Gemini vision could not generate a response with the configured API key. "
            "The key is being sent securely via the x-goog-api-key header. "
            f"Tried: {', '.join(self._candidate_models())}. "
            f"Details: {detail}"
        )
