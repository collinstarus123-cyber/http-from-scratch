import socket
import subprocess
import sys
import time

import pytest

from proxy import RoundRobin
from server import make_response, parse_request, route

HOST, PORT = "127.0.0.1", 8080


# ---------- Unit tests: test one function, no server needed ----------

def test_parse_request_reads_first_line_and_headers():
    raw = b"GET /about HTTP/1.1\r\nHost: localhost\r\nUser-Agent: test\r\n\r\n"
    method, path, version, headers = parse_request(raw)
    assert method == "GET"
    assert path == "/about"
    assert version == "HTTP/1.1"
    assert headers["user-agent"] == "test"


def test_parse_request_rejects_garbage():
    with pytest.raises(ValueError):
        parse_request(b"this is not http\r\n\r\n")


def test_route_known_and_unknown_paths():
    assert route("/", {})[0] == "200 OK"
    assert route("/about", {})[0] == "200 OK"
    assert route("/banana", {})[0] == "404 Not Found"


def test_make_response_content_length_is_correct():
    reply = make_response("200 OK", "hello")
    assert b"Content-Length: 5" in reply
    assert reply.endswith(b"hello")


# ---------- Integration tests: start the real server and talk to it ----------

@pytest.fixture(scope="module")
def running_server():
    try:
        socket.create_connection((HOST, PORT), timeout=0.5).close()
        pytest.fail("Port 8080 is already in use. Stop any running server first.")
    except OSError:
        pass  # nothing is listening, which is what we want

    process = subprocess.Popen([sys.executable, "server.py"])
    for _ in range(50):
        try:
            socket.create_connection((HOST, PORT), timeout=0.2).close()
            break
        except OSError:
            time.sleep(0.1)
    else:
        process.terminate()
        pytest.fail("Server did not start in time.")

    yield

    process.terminate()
    process.wait()


def send(raw):
    with socket.create_connection((HOST, PORT), timeout=5) as s:
        s.sendall(raw)
        chunks = []
        while True:
            chunk = s.recv(4096)
            if not chunk:
                break
            chunks.append(chunk)
    return b"".join(chunks)


def test_about_returns_200(running_server):
    reply = send(b"GET /about HTTP/1.1\r\nHost: x\r\n\r\n")
    assert reply.startswith(b"HTTP/1.1 200 OK")
    assert b"built this server" in reply


def test_unknown_page_returns_404(running_server):
    reply = send(b"GET /banana HTTP/1.1\r\nHost: x\r\n\r\n")
    assert reply.startswith(b"HTTP/1.1 404")


def test_garbage_returns_400_and_server_survives(running_server):
    reply = send(b"this is not http\r\n\r\n")
    assert reply.startswith(b"HTTP/1.1 400")
    after = send(b"GET / HTTP/1.1\r\nHost: x\r\n\r\n")
    assert after.startswith(b"HTTP/1.1 200")


def test_silent_client_does_not_block_others(running_server):
    silent = socket.create_connection((HOST, PORT))
    try:
        start = time.time()
        reply = send(b"GET /about HTTP/1.1\r\nHost: x\r\n\r\n")
        elapsed = time.time() - start
        assert reply.startswith(b"HTTP/1.1 200")
        assert elapsed < 2
    finally:
        silent.close()
def test_static_index_is_served(running_server):
    reply = send(b"GET / HTTP/1.1\r\nHost: x\r\n\r\n")
    assert reply.startswith(b"HTTP/1.1 200")
    assert b"text/html" in reply


def test_path_traversal_is_blocked(running_server):
    for evil in ["/../server.py", "/..%2fserver.py", "/%2e%2e/server.py"]:
        reply = send(f"GET {evil} HTTP/1.1\r\nHost: x\r\n\r\n".encode())
        assert b"def make_response" not in reply
        assert reply.startswith(b"HTTP/1.1 403")
def test_whoami_reports_the_port():
    status, body, _ = route("/whoami", {})
    assert status == "200 OK"
    assert "port" in body


def test_round_robin_alternates():
    pool = RoundRobin([("a", 1), ("b", 2)])
    picks = [pool.next() for _ in range(4)]
    assert picks == [("a", 1), ("b", 2), ("a", 1), ("b", 2)]


def test_health_route_is_ok():
    status, body, _ = route("/health", {})
    assert status == "200 OK"
    assert body == "ok"


def test_round_robin_skips_unhealthy_backends():
    pool = RoundRobin([("a", 1), ("b", 2)])
    pool.set_health(("b", 2), False)
    assert [pool.next() for _ in range(3)] == [("a", 1)] * 3


def test_round_robin_returns_none_when_all_are_down():
    pool = RoundRobin([("a", 1)])
    pool.set_health(("a", 1), False)
    assert pool.next() is None


def test_backend_rejoins_after_recovering():
    pool = RoundRobin([("a", 1), ("b", 2)])
    pool.set_health(("b", 2), False)
    assert pool.set_health(("b", 2), True) is True
    assert ("b", 2) in [pool.next() for _ in range(2)]
    