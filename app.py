from http.server import HTTPServer, BaseHTTPRequestHandler
import socketserver
import urllib.parse
import os
import mimetypes
import json
import pathlib
import socket
import threading
from datetime import datetime

PORT_HTTP = 3000
PORT_UDP = 5000


class MyHandler(BaseHTTPRequestHandler):
    BASE_DIR = pathlib.Path(__file__).parent.resolve()
    def do_GET(self):
        pr_url = urllib.parse.urlparse(self.path)
        if pr_url.path == "/":
            self.send_html_file("front-init/templates/index.html")
        elif pr_url.path == "/messages":
            self.send_html_file("front-init/templates/message.html")
        elif pr_url.path.startswith("/front-init/static/"):
            filepath = pr_url.path.lstrip("/")
            self.send_static(filepath)
        elif pr_url.path == "/messages.json":
            data_file = self.BASE_DIR / "front-init/storage/data.json"
            if data_file.exists():
                self.send_response(200)
                self.send_header("Content-type", "application/json; charset=utf-8")
                self.end_headers()
                with open(data_file, "rb") as f:
                    self.wfile.write(f.read())
            else:
                self.send_error(404, "Messages data not found")
        else:
            self.send_html_file("front-init/templates/error.html", 404)
    
    def do_POST(self):
        if self.path == "/message":
            content_length = int(self.headers.get("Content-Length", 0))
            post_data = self.rfile.read(content_length).decode("utf-8")
            post_params = urllib.parse.parse_qs(post_data)

            username = post_params.get("username", [""])[0]
            message = post_params.get("message", [""])[0]

            data_file = self.BASE_DIR / "front-init/storage/data.json"
            os.makedirs(data_file.parent, exist_ok=True)

            if data_file.exists():
                with open(data_file, "r", encoding="utf-8") as f:
                    try:
                        data = json.load(f)
                        if not isinstance(data, list):
                            data = []
                    except json.JSONDecodeError:
                        data = []
            else:
                data = []

            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            data.append({"username": username, "message": message, "timestamp": timestamp})
            print(f"[DEBUG] Received: username={username}, message={message}")

            with open(data_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            self.send_response(303)
            self.send_header("Location", "/messages")
            self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()


    def send_html_file(self, filename, status=200):
        try:
            with open(filename, "rb") as fd:
                self.send_response(status)
                self.send_header("Content-type", "text/html")
                self.end_headers()
                self.wfile.write(fd.read())
        except FileNotFoundError:
            self.send_response(404)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(b"<h1>404 File Not Found</h1>")
    
    def send_static(self, filepath):
        path = self.BASE_DIR / filepath
        if path.is_file():
            self.send_response(200)
            mime, _ = mimetypes.guess_type(str(path))
            self.send_header("Content-type", mime or "application/octet-stream")
            self.end_headers()
            with open(path, "rb") as f:
                self.wfile.write(f.read())
        else:
            self.send_error(404, "Not Found")
    
def udp_server():
    BASE_DIR = pathlib.Path(__file__).parent.resolve()
    data_file = BASE_DIR / "front-init/storage/data.json"
    data_file.parent.mkdir(parents=True, exist_ok=True)

    if not data_file.exists():
        with open(data_file, "w", encoding="utf-8") as f:
            json.dump([], f, ensure_ascii=False, indent=2)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", PORT_UDP))
    print(f"UDP server listening on port {PORT_UDP}")

    while True:
        data, addr = sock.recvfrom(4096)
        try:
            msg_dict = json.loads(data.decode("utf-8"))
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
            msg_dict["timestamp"] = timestamp

            with open(data_file, "r+", encoding="utf-8") as f:
                try:
                    existing_data = json.load(f)
                    if not isinstance(existing_data, list):
                        existing_data = []
                except json.JSONDecodeError:
                    existing_data = []

                existing_data.append(msg_dict)

                f.seek(0)
                json.dump(existing_data, f, ensure_ascii=False, indent=2)
                f.truncate()
            print(f"Saved UDP message from {addr}: {msg_dict}")
        except Exception as e:
            print("UDP server error:", e)
    
            
if __name__ == "__main__":
    udp_thread = threading.Thread(target=udp_server, daemon=True)
    udp_thread.start()

    with socketserver.TCPServer(("", PORT_HTTP), MyHandler) as httpd:
        print(f"Serving HTTP on port {PORT_HTTP}")
        httpd.serve_forever()
