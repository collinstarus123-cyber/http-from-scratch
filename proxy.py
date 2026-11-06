import argparse
import itertools
import socket
import sys
import threading

HOST = "127.0.0.1"


def make_error(status, message):
    body = message.encode()
    return (
        f"HTTP/1.1 {status}\r\n"
        "Content-Type: text/plain; charset=utf-8\r\n"
        f"Content-Length: {len(body)}\r\n"
        "Connection: close\r\n"
        "\r\n"
    ).encode() + body


class RoundRobin:
    def __init__(self, backends):
        self._cycle = itertools.cycle(backends)
        self._lock = threading.Lock()

    def next(self):
        with self._lock:
            return next(self._cycle)


def parse_backends(text):
    backends = []
    for item in text.split(","):
        host, _, port = item.strip().rpartition(":")
        backends.append((host, int(port)))
    return backends


def forward(request_bytes, backend):
    with socket.create_connection(backend, timeout=5) as upstream:
        upstream.sendall(request_bytes)
        chunks = []
        while True:
            chunk = upstream.recv(4096)
            if not chunk:
                break
            chunks.append(chunk)
    return b"".join(chunks)


def handle_client(conn, pool):
    conn.settimeout(5)
    try:
        request = conn.recv(4096)
        if not request:
            return

        backend = pool.next()
        print(f"forwarding to port {backend[1]}")
        try:
            reply = forward(request, backend)
        except OSError:
            conn.sendall(make_error("502 Bad Gateway", "Backend unavailable"))
            return

        conn.sendall(reply)
    except Exception as error:
        print("Proxy error:", error)
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="A tiny round-robin reverse proxy.")
    parser.add_argument("--port", type=int, default=8080, help="port the proxy listens on")
    parser.add_argument(
        "--backends",
        default="127.0.0.1:9001,127.0.0.1:9002",
        help="comma-separated list of host:port",
    )
    args = parser.parse_args()
    pool = RoundRobin(parse_backends(args.backends))

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    if sys.platform != "win32":
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, args.port))
    server.listen()
    server.settimeout(1)
    print(f"Proxy running at http://{HOST}:{args.port} -> {args.backends}")

    try:
        while True:
            try:
                conn, addr = server.accept()
            except socket.timeout:
                continue
            threading.Thread(target=handle_client, args=(conn, pool)).start()
    except KeyboardInterrupt:
        print("\nShutting down.")
    finally:
        server.close()


if __name__ == "__main__":
    main()