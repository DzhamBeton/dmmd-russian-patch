#!/usr/bin/env python3
"""Small local translation editor for a DMMD JSONL catalog."""

from __future__ import annotations

import argparse
import json
import re
import threading
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
VOICE_PREFIX_RE = re.compile(r"(?ms)^(\s*//【[^\r\n]*】\s*\r?\n<voice[^>]+>\s*)")


class Catalog:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.lock = threading.Lock()
        self.rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
        self.by_id = {row["id"]: row for row in self.rows}

    @staticmethod
    def visible(text: str) -> str:
        match = VOICE_PREFIX_RE.match(text)
        return text[len(match.group(1)) :] if match else text

    def public_rows(self) -> list[dict]:
        result = []
        for row in self.rows:
            source = row.get("source", "")
            translation = row.get("translation", "")
            result.append(
                {
                    "id": row["id"],
                    "file": row.get("file", ""),
                    "source": self.visible(source),
                    "translation": self.visible(translation),
                    "draftTranslation": self.visible(row.get("draft_translation", "")),
                    "status": row.get("status", "new"),
                    "polishStatus": row.get("polish_status", ""),
                    "hasVoice": "<voice" in source,
                }
            )
        return result

    def update(self, record_id: str, translation: str, status: str) -> None:
        with self.lock:
            row = self.by_id[record_id]
            source_match = VOICE_PREFIX_RE.match(row.get("source", ""))
            prefix = source_match.group(1) if source_match else ""
            row["translation"] = prefix + translation
            row["status"] = status
            temporary = self.path.with_suffix(self.path.suffix + ".tmp")
            with temporary.open("w", encoding="utf-8", newline="\n") as stream:
                for item in self.rows:
                    stream.write(json.dumps(item, ensure_ascii=False) + "\n")
            temporary.replace(self.path)


def make_handler(catalog: Catalog):
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(ROOT / "editor"), **kwargs)

        def send_json(self, payload: object, status: int = 200) -> None:
            encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def do_GET(self) -> None:
            path = urlparse(self.path).path
            if path == "/api/catalog":
                self.send_json({"path": str(catalog.path), "records": catalog.public_rows()})
                return
            if path == "/":
                self.path = "/index.html"
            super().do_GET()

        def do_POST(self) -> None:
            if urlparse(self.path).path != "/api/record":
                self.send_json({"error": "not found"}, 404)
                return
            try:
                size = int(self.headers.get("Content-Length", "0"))
                data = json.loads(self.rfile.read(size))
                catalog.update(data["id"], data.get("translation", ""), data.get("status", "reviewed"))
                self.send_json({"ok": True})
            except (KeyError, ValueError, json.JSONDecodeError) as error:
                self.send_json({"error": str(error)}, 400)

        def log_message(self, format: str, *args) -> None:
            if not args or not str(args[0]).startswith("GET /api/catalog"):
                super().log_message(format, *args)

    return Handler


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("catalog", nargs="?", type=Path, default=ROOT / "translations" / "ru-machine.jsonl")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-open", action="store_true")
    args = parser.parse_args()
    path = args.catalog.resolve()
    if not path.exists():
        raise SystemExit(f"Catalog does not exist: {path}\nRun scripts/start_translation.ps1 first.")
    catalog = Catalog(path)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(catalog))
    url = f"http://127.0.0.1:{args.port}"
    print(f"Editing {path}")
    print(f"Open {url} (Ctrl+C to stop)")
    if not args.no_open:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    server.serve_forever()


if __name__ == "__main__":
    main()
