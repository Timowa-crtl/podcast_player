"""Minimal web editor for config.json (podcast feeds, music_dir, albums).

Runs a stdlib HTTP server in a daemon thread. One page, one form, no JS.
Each of the 12 rows per section is a knob position; an empty row is saved
as null so slot N always maps to knob position N.

Only podcasts, albums and music_dir are touched; every other key in
config.json is preserved. Writes are atomic and keep config.json.bak.
"""

import html
import json
import os
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable, Optional
from urllib.parse import parse_qs

from config import DEFAULTS, MAX_SLOTS, ensure_config, validate
from music_manager import natural_sort_key
from utils import log

MAX_BODY_BYTES = 64 * 1024

CSS = """
body{font:15px/1.4 system-ui,sans-serif;max-width:820px;margin:1.5em auto;padding:0 1em;color:#222}
h1{font-size:1.3em}h2{font-size:1.05em;margin-top:1.6em}
table{width:100%;border-collapse:collapse}td{padding:2px 3px}
td.n{width:1.6em;color:#888;text-align:right}
input,select{width:100%;box-sizing:border-box;font:inherit;padding:3px}
.msg{padding:.5em .8em;margin:1em 0}.ok{background:#e6f4e6}.err{background:#fbe5e5}
.hint{color:#777;font-size:.9em}button{font:inherit;padding:.4em 1.6em;margin:1.5em 0}
"""


def _slots(items: list) -> list:
    """Pad/trim a config list to exactly MAX_SLOTS entries (None = empty)."""
    items = list(items or [])[:MAX_SLOTS]
    return items + [None] * (MAX_SLOTS - len(items))


def _trim(items: list) -> list:
    """Drop trailing empty slots."""
    while items and items[-1] is None:
        items.pop()
    return items


def _list_folders(music_dir: str) -> list:
    try:
        return sorted(
            (d.name for d in Path(music_dir).iterdir() if d.is_dir()),
            key=natural_sort_key,
        )
    except OSError:
        return []


class ConfigEditor:
    """Reads, validates and atomically writes config.json."""

    def __init__(self, config_path: str, on_saved: Optional[Callable] = None):
        self.path = Path(config_path)
        self.on_saved = on_saved
        self._lock = threading.Lock()

    def load(self) -> dict:
        with open(self.path) as f:
            return json.load(f)

    def form_values(self) -> dict:
        """Current config as the values the form shows."""
        data = self.load()
        return {
            "music_dir": data.get("music_dir", DEFAULTS["music_dir"]),
            "podcasts": [
                {"name": p.get("name", ""), "rss_url": p.get("rss_url", "")} if p else None
                for p in _slots(data.get("podcasts"))
            ],
            "albums": [
                {"folder": a.get("folder", ""), "name": a.get("name", "")} if a else None
                for a in _slots(data.get("albums"))
            ],
        }

    @staticmethod
    def parse_form(form: dict) -> tuple:
        """Turn POSTed fields into (values, errors)."""

        def get(key):
            return form.get(key, [""])[0].strip()

        errors = []
        podcasts, albums = [], []
        for n in range(1, MAX_SLOTS + 1):
            name, url = get(f"p{n}_name"), get(f"p{n}_url")
            if not name and not url:
                podcasts.append(None)
                continue
            podcasts.append({"name": name, "rss_url": url})
            if not name:
                errors.append(f"Podcast {n}: name is missing")
            if not url.startswith(("http://", "https://")):
                errors.append(f"Podcast {n}: feed URL must start with http:// or https://")
        for n in range(1, MAX_SLOTS + 1):
            folder, aname = get(f"a{n}_folder"), get(f"a{n}_name")
            if not folder and not aname:
                albums.append(None)
                continue
            albums.append({"folder": folder, "name": aname})
            if not folder:
                errors.append(f"Album {n}: pick a folder")

        music_dir = get("music_dir")
        if not music_dir:
            errors.append("Music folder is missing")
        if not any(podcasts):
            errors.append("At least one podcast is required")

        return {"music_dir": music_dir, "podcasts": podcasts, "albums": albums}, errors

    def save(self, values: dict):
        """Merge values into config.json and write it atomically."""
        with self._lock:
            data = self.load()
            data["music_dir"] = values["music_dir"]
            data["podcasts"] = _trim(list(values["podcasts"]))
            albums = []
            for a in values["albums"]:
                if a and not a["name"]:
                    a = {"folder": a["folder"]}  # name defaults to folder
                albums.append(a)
            # All slots empty -> [] so the player auto-discovers folders
            data["albums"] = _trim(albums)
            validate(data)

            text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
            tmp = self.path.with_suffix(".json.tmp")
            tmp.write_text(text, encoding="utf-8")
            if self.path.exists():
                bak = self.path.with_suffix(".json.bak")
                bak.write_bytes(self.path.read_bytes())
            os.replace(tmp, self.path)

        log("INFO", "Config saved via web editor")
        if self.on_saved:
            self.on_saved()


def render_page(values: dict, errors: list = None, saved: bool = False) -> str:
    e = lambda s: html.escape(s or "", quote=True)
    out = [
        "<!DOCTYPE html><html><head><meta charset='utf-8'>",
        "<meta name='viewport' content='width=device-width,initial-scale=1'>",
        f"<title>KnobFM settings</title><style>{CSS}</style></head><body>",
        "<h1>KnobFM settings</h1>",
    ]
    if saved:
        out.append("<div class='msg ok'>Saved. Changes are applied now.</div>")
    if errors:
        items = "".join(f"<li>{e(x)}</li>" for x in errors)
        out.append(f"<div class='msg err'>Not saved:<ul>{items}</ul></div>")

    out.append("<form method='post' action='/'>")

    out.append("<h2>Podcasts</h2><table>")
    for n, p in enumerate(values["podcasts"], 1):
        p = p or {}
        out.append(
            f"<tr><td class='n'>{n}</td>"
            f"<td style='width:32%'><input name='p{n}_name' value='{e(p.get('name'))}' placeholder='Name'></td>"
            f"<td><input name='p{n}_url' value='{e(p.get('rss_url'))}' placeholder='Feed URL'></td></tr>"
        )
    out.append("</table>")

    music_dir = values["music_dir"]
    folders = _list_folders(music_dir)
    out.append("<h2>Music</h2>")
    out.append(
        f"<p>Music folder <input name='music_dir' value='{e(music_dir)}'></p>"
        "<p class='hint'>Save after changing the music folder to refresh the folder lists. "
        "Leave every album empty to use the first 12 folders alphabetically.</p>"
    )
    if not folders:
        out.append("<p class='msg err'>No subfolders found in the music folder.</p>")

    out.append("<table>")
    for n, a in enumerate(values["albums"], 1):
        a = a or {}
        current = a.get("folder", "")
        opts = ["<option value=''>(empty)</option>"]
        if current and current not in folders:
            opts.append(f"<option value='{e(current)}' selected>{e(current)} (missing)</option>")
        for f in folders:
            sel = " selected" if f == current else ""
            opts.append(f"<option value='{e(f)}'{sel}>{e(f)}</option>")
        out.append(
            f"<tr><td class='n'>{n}</td>"
            f"<td><select name='a{n}_folder'>{''.join(opts)}</select></td>"
            f"<td style='width:35%'><input name='a{n}_name' value='{e(a.get('name'))}' placeholder='Display name (optional)'></td></tr>"
        )
    out.append("</table>")

    out.append("<button type='submit'>Save</button></form></body></html>")
    return "".join(out)


def _make_handler(editor: ConfigEditor):
    class Handler(BaseHTTPRequestHandler):
        def _send(self, status: int, body: str = "", headers: dict = None):
            data = body.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            for k, v in (headers or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            path, _, query = self.path.partition("?")
            if path != "/":
                return self._send(404, "Not found")
            try:
                values = editor.form_values()
            except (OSError, ValueError) as ex:
                return self._send(500, f"Cannot read config: {html.escape(str(ex))}")
            self._send(200, render_page(values, saved=query == "saved=1"))

        def do_POST(self):
            if self.path != "/":
                return self._send(404, "Not found")
            length = int(self.headers.get("Content-Length") or 0)
            if length > MAX_BODY_BYTES:
                return self._send(413, "Too large")
            form = parse_qs(self.rfile.read(length).decode("utf-8"), keep_blank_values=True)
            values, errors = editor.parse_form(form)
            if not errors:
                try:
                    editor.save(values)
                except (OSError, ValueError) as ex:
                    errors = [str(ex)]
            if errors:
                return self._send(400, render_page(values, errors=errors))
            self._send(303, headers={"Location": "/?saved=1"})

        def log_message(self, fmt, *args):
            log("DEBUG", f"web: {self.address_string()} {fmt % args}")

    return Handler


class WebConfigServer:
    """Background HTTP server for the config editor."""

    def __init__(self, port: int, config_path: str = "config.json",
                 on_saved: Optional[Callable] = None, host: str = "0.0.0.0"):
        self.port = port
        self.host = host
        self.editor = ConfigEditor(config_path, on_saved)
        self._server = None

    def start(self):
        if not self.port:
            log("INFO", "Web config editor disabled (web_port = 0)")
            return
        try:
            self._server = ThreadingHTTPServer((self.host, self.port), _make_handler(self.editor))
        except OSError as e:
            log("WARNING", f"Web config editor not started on port {self.port}: {e}")
            return
        self._server.daemon_threads = True
        threading.Thread(target=self._server.serve_forever, daemon=True, name="web-config").start()
        log("INFO", f"Web config editor on http://{socket.gethostname()}.local:{self.port}/")

    def stop(self):
        if self._server:
            self._server.shutdown()
            self._server.server_close()
            self._server = None


if __name__ == "__main__":
    # Standalone: edit config.json without running the player.
    import time

    ensure_config()
    try:
        port = json.loads(Path("config.json").read_text()).get("web_port", DEFAULTS["web_port"])
    except (OSError, ValueError):
        port = DEFAULTS["web_port"]
    server = WebConfigServer(port)
    server.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        server.stop()
