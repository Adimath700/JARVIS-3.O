import json
import os
import threading
import uuid
import webbrowser
from datetime import timedelta
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from livekit import api

from jarvis.ui.state import ui_state

WEB_ROOT = Path(__file__).with_name("web")
STATIC_FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/styles.css": ("styles.css", "text/css; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
}

_server = None
_server_lock = threading.Lock()


def create_participant_credentials() -> dict[str, str]:
    server_url = os.getenv("LIVEKIT_URL", "").strip()
    api_key = os.getenv("LIVEKIT_API_KEY", "").strip()
    api_secret = os.getenv("LIVEKIT_API_SECRET", "").strip()
    agent_name = os.getenv("LIVEKIT_AGENT_NAME", "jarvis").strip()
    if not server_url or not api_key or not api_secret:
        raise RuntimeError(
            "LIVEKIT_URL, LIVEKIT_API_KEY, and LIVEKIT_API_SECRET "
            "must be configured in .env"
        )

    room_name = f"jarvis-{uuid.uuid4().hex[:12]}"
    identity = f"user-{uuid.uuid4().hex[:10]}"
    token = (
        api.AccessToken(api_key, api_secret)
        .with_identity(identity)
        .with_name("JARVIS User")
        .with_ttl(timedelta(minutes=30))
        .with_grants(
            api.VideoGrants(
                room_join=True,
                room=room_name,
                can_publish=True,
                can_subscribe=True,
                can_publish_data=True,
            )
        )
        .with_room_config(
            api.RoomConfiguration(
                agents=[
                    api.RoomAgentDispatch(
                        agent_name=agent_name,
                        metadata='{"client":"jarvis-holographic-ui"}',
                    )
                ]
            )
        )
        .to_jwt()
    )
    return {
        "server_url": server_url,
        "participant_token": token,
        "room_name": room_name,
    }


class JarvisUiHandler(BaseHTTPRequestHandler):
    server_version = "JarvisUi/1.0"

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/api/state":
            self._send_json(ui_state.snapshot())
            return
        if path == "/api/token":
            try:
                self._send_json(create_participant_credentials())
            except RuntimeError as exc:
                self._send_json(
                    {"error": str(exc)},
                    status=HTTPStatus.SERVICE_UNAVAILABLE,
                )
            return

        static = STATIC_FILES.get(path)
        if static is None:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        filename, content_type = static
        body = (WEB_ROOT / filename).read_bytes()
        self._send_bytes(body, content_type)

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        if not path.startswith("/api/approvals/"):
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        request_id = path.rsplit("/", 1)[-1]
        try:
            length = min(int(self.headers.get("Content-Length", "0")), 4096)
            payload = json.loads(self.rfile.read(length) or b"{}")
            approved = payload["approved"]
            if not isinstance(approved, bool):
                raise ValueError
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            self._send_json(
                {"error": "Expected a JSON boolean named approved"},
                status=HTTPStatus.BAD_REQUEST,
            )
            return

        resolved = ui_state.resolve_approval(request_id, approved)
        if not resolved:
            self._send_json(
                {"error": "Approval request not found or already resolved"},
                status=HTTPStatus.NOT_FOUND,
            )
            return
        self._send_json({"resolved": True, "approved": approved})

    def _send_json(self, payload: dict, status=HTTPStatus.OK):
        body = json.dumps(payload).encode("utf-8")
        self._send_bytes(body, "application/json; charset=utf-8", status)

    def _send_bytes(
        self,
        body: bytes,
        content_type: str,
        status=HTTPStatus.OK,
    ):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; "
            "script-src 'self' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src https://fonts.gstatic.com; "
            "connect-src 'self' https: wss:; "
            "media-src 'self' blob:; "
            "img-src 'self' data:",
        )
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        return


def start_ui_server(open_browser: bool = True) -> ThreadingHTTPServer:
    global _server
    with _server_lock:
        if _server is not None:
            return _server

        host = "127.0.0.1"
        port = int(os.getenv("JARVIS_UI_PORT", "8765"))
        _server = ThreadingHTTPServer((host, port), JarvisUiHandler)
        _server.daemon_threads = True
        thread = threading.Thread(
            target=_server.serve_forever,
            name="jarvis-ui",
            daemon=True,
        )
        thread.start()
        url = f"http://{host}:{port}"
        print(f"JARVIS holographic UI: {url}")
        auto_open = os.getenv("JARVIS_UI_AUTO_OPEN", "true").lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        if open_browser and auto_open:
            threading.Timer(0.8, webbrowser.open, args=(url,)).start()
        return _server
