from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .app import ProjectService, create_project_service

ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = ROOT / "static"


class PlotRequestHandler(BaseHTTPRequestHandler):
    service: ProjectService

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._serve_index()
            return
        if parsed.path == "/api/health":
            self._send_json({"status": "ok"})
            return
        if parsed.path == "/api/projects":
            self._send_json({"projects": self.service.list_projects()})
            return
        if parsed.path.startswith("/api/projects/"):
            project_id = parsed.path.removeprefix("/api/projects/").strip("/")
            project = self.service.get_project(project_id)
            if not project:
                self._send_json({"error": "project not found"}, status=HTTPStatus.NOT_FOUND)
                return
            self._send_json(project)
            return
        self._send_json({"error": "not found"}, status=HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        try:
            body = self._read_json()
            if parsed.path == "/api/projects":
                project = self.service.create_project(body.get("title", "未命名项目"), body.get("seed_text", ""))
                self._send_json(project, status=HTTPStatus.CREATED)
                return
            if parsed.path.endswith("/simulate"):
                project_id = parsed.path.split("/")[3]
                scene = self.service.simulate(project_id, int(body.get("rounds", 1)))
                self._send_json(scene)
                return
            if parsed.path.endswith("/summary"):
                project_id = parsed.path.split("/")[3]
                export = self.service.summarize(project_id, body.get("style", "网文"))
                self._send_json(export)
                return
            if parsed.path.endswith("/branch"):
                project_id = parsed.path.split("/")[3]
                branch = self.service.branch(project_id, body.get("snapshot_id", ""), body.get("branch_name", "新分支"))
                self._send_json(branch, status=HTTPStatus.CREATED)
                return
            self._send_json({"error": "not found"}, status=HTTPStatus.NOT_FOUND)
        except KeyError as exc:
            self._send_json({"error": str(exc)}, status=HTTPStatus.NOT_FOUND)
        except (ValueError, json.JSONDecodeError) as exc:
            self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return

    def _serve_index(self) -> None:
        content = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(content.encode("utf-8"))

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length).decode("utf-8") if length else "{}"
        return json.loads(raw or "{}")

    def _send_json(self, payload: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
        content = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)


def build_server(host: str = "127.0.0.1", port: int = 8000, data_dir: str | None = None) -> ThreadingHTTPServer:
    service = create_project_service(data_dir)
    handler = type("ConfiguredPlotRequestHandler", (PlotRequestHandler,), {"service": service})
    return ThreadingHTTPServer((host, port), handler)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Run the Plot System web server.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--data-dir", default=None)
    args = parser.parse_args()

    server = build_server(host=args.host, port=args.port, data_dir=args.data_dir)
    print(f"Plot System running at http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
