import socket
import subprocess
import sys
import time

import pytest

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