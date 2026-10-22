"""Only synthetic metrics. No access to any monitored host or execution API."""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Lock

state = {"scenario": "outage"}
lock = Lock()
values = {"outage": (0, 94, 12, 25), "warning": (1, 91, 8, 0), "normal": (1, 30, 0, 0)}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/metrics":
            self.send_error(404)
            return
        with lock:
            database, disk, packets, http = values[state["scenario"]]
        body = (f"demo_database_up {database}\ndemo_disk_used_percent {disk}\n"
                f"demo_packet_loss_percent {packets}\ndemo_http_error_percent {http}\ndemo_health_check 1\n").encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; version=0.0.4")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        try:
            if self.path != "/scenario" or int(self.headers.get("Content-Length", 0)) > 1000:
                raise ValueError()
            payload = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
            if payload["scenario"] not in values:
                raise ValueError()
            with lock:
                state["scenario"] = payload["scenario"]
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"ok":true}')
        except (ValueError, KeyError):
            self.send_error(400)


ThreadingHTTPServer(("0.0.0.0", 9101), Handler).serve_forever()
