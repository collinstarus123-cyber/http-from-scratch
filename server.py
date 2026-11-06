import argparse
import mimetypes
import socket
import sys
import threading
from pathlib import Path
from urllib.parse import unquote, urlsplit

HOST = "127.0.0.1"
PORT = 8080
PUBLIC = (Path(__file__).parent / "public").resolve()
TEXT = "text/plain; charset=utf-8"


def make_response(status, body, content_type=TEXT):
    body_bytes = body.encode() if isinstance(body, str) else body
    return (
        f"HTTP/1.1 {status}\r\n"
        f"Content-Type: {content_type}\r\n"
        f"Content-Length: {len(body_bytes)}\r\n"
        "Connection: close\r\n"
        "\r\n"
    ).encode() + body_bytes


def parse_request(data):
    text = data.decode()
    lines = text.split("\r\n")
    method, path, version = lines[0].split(" ")

    headers = {}
    for line in lines[1:]:
        if line == "":
            break
        name, _, value = line.partition(":")
        headers[name.strip().lower()] = value.strip()

    return method, path, version, headers


def serve_static(path):
    try:
        clean = unquote(urlsplit(path).path)
        target = (PUBLIC / clean.lstrip("/")).resolve()
    except (ValueError, OSError):
        return "400 Bad Request", "Bad request", TEXT

    if not target.is_relative_to(PUBLIC):
        return "403 Forbidden", "Forbidden", TEXT
    if target.is_dir():
        target = target / "index.html"
    if not target.is_file():
        return "404 Not Found", "Page not found", TEXT

    content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
    if content_type.startswith("text/"):
        content_type += "; charset=utf-8"
    return "200 OK", target.read_bytes(), content_type


def route(path, headers):
    clean = urlsplit(path).path
    if clean == "/about":
        return "200 OK", "I built this server myself, from scratch.", TEXT
    if clean == "/whoami":
        return "200 OK", f"Answered by the server on port {PORT}", TEXT
    if clean == "/health":
        return "200 OK", "ok", TEXT
    if clean == "/headers":
        body = "\n".join(f"{name}: {value}" for name, value in headers.items())
        return "200 OK", body, TEXT
    return serve_static(path)


def handle_client(conn):
    conn.settimeout(5)
    try:
        data = conn.recv(4096)
        if not data:
            return

        try:
            method, path, version, headers = parse_request(data)
        except ValueError:
            conn.sendall(make_response("400 Bad Request", "Bad request"))
            return

        print(method, path, "| browser:", headers.get("user-agent"))
        status, body, content_type = route(path, headers)
        conn.sendall(make_response(status, body, content_type))
    except Exception as error:
        print("Error handling request:", error)
    finally:
        conn.close()


def main():
    global PORT
    parser = argparse.ArgumentParser(description="A small HTTP server built on raw sockets.")
    parser.add_argument("--port", type=int, default=8080, help="port to listen on (default 8080)")
    args = parser.parse_args()
    PORT = args.port

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    if sys.platform != "win32":
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen()
    server.settimeout(1)
    print(f"Server is running at http://{HOST}:{PORT}")

    try:
        while True:
            try:
                conn, addr = server.accept()
            except socket.timeout:
                continue
            thread = threading.Thread(target=handle_client, args=(conn,))
            thread.start()
    except KeyboardInterrupt:
        print("\nShutting down.")
    finally:
        server.close()


if __name__ == "__main__":
    main()