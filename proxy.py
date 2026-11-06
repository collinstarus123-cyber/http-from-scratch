import argparse
import socket
import sys
import threading
import time

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
        self._backends = list(backends)
        self._healthy = set(backends)
        self._index = 0
        self._lock = threading.Lock()

    @property
    def backends(self):
        return list(self._backends)

    def next(self):
        with self._lock:
            for _ in range(len(self._backends)):
                backend = self._backends[self._index % len(self._backends)]
                self._index += 1
                if backend in self._healthy:
                    return backend
            return None

    def set_health(self, backend, is_healthy):
        """Record a backend's health. Returns True if its state changed."""
        with self._lock:
            was_healthy = backend in self._healthy
            if is_healthy:
                self._healthy.add(backend)
            else:
                self._healthy.discard(backend)
        return was_healthy != is_healthy


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


def is_alive(backend):
    try:
        with socket.create_connection(backend, timeout=1) as s:
            s.sendall(b"GET /health HTTP/1.1\r\nHost: proxy\r\nConnection: close\r\n\r\n")
            return s.recv(64).startswith(b"HTTP/1.1 200")
    except OSError:
        return False


def health_loop(pool, interval):
    while True:
        for backend in pool.backends:
            alive = is_alive(backend)
            if pool.set_health(backend, alive):
                print(f"backend {backend[1]} is {'UP' if alive else 'DOWN'}")
        time.sleep(interval)


def handle_client(conn, pool):
    conn.settimeout(5)
    try:
        request = conn.recv(4096)
        if not request:
            return

        reply = None
        for _ in range(len(pool.backends)):
            backend = pool.next()
            if backend is None:
                break
            try:
                reply = forward(request, backend)
                break
            except OSError:
                if pool.set_health(backend, False):
                    print(f"backend {backend[1]} is DOWN")

        if reply is None:
            conn.sendall(make_error("503 Service Unavailable", "No healthy backends"))
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
    parser.add_argument("--interval", type=float, default=2, help="seconds between health checks")
    args = parser.parse_args()
    pool = RoundRobin(parse_backends(args.backends))

    threading.Thread(target=health_loop, args=(pool, args.interval), daemon=True).start()

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