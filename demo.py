import argparse
import socket
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).parent
HOST = "127.0.0.1"
PROXY_PORT = 8080
BACKEND_PORTS = [9001, 9002]


def port_is_open(port):
    try:
        socket.create_connection((HOST, port), timeout=0.5).close()
        return True
    except OSError:
        return False


def wait_until_open(port, timeout=10):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if port_is_open(port):
            return
        time.sleep(0.1)
    raise RuntimeError(f"Nothing started listening on port {port}")


def start(script, *args, quiet=True):
    output = subprocess.DEVNULL if quiet else None
    return subprocess.Popen(
        [sys.executable, str(HERE / script), *args],
        stdout=output,
        stderr=output,
    )


def fetch(path):
    with socket.create_connection((HOST, PROXY_PORT), timeout=10) as s:
        s.sendall(
            f"GET {path} HTTP/1.1\r\nHost: demo\r\nConnection: close\r\n\r\n".encode()
        )
        data = b""
        while True:
            chunk = s.recv(4096)
            if not chunk:
                break
            data += chunk
    return data.partition(b"\r\n\r\n")[2].decode(errors="replace")


def show_requests(count=6):
    answers = []
    for i in range(1, count + 1):
        try:
            answer = fetch("/whoami")
        except OSError as error:
            answer = f"FAILED ({error})"
        print(f"  request {i}: {answer}")
        answers.append(answer)
    return answers


def heading(text):
    print(f"\n=== {text} ===")


def check(failures, condition, message):
    if condition:
        print(f"  [OK] {message}")
    else:
        print(f"  [FAIL] {message}")
        failures.append(message)


def served_by(answers):
    return {port for port in BACKEND_PORTS if any(str(port) in a for a in answers)}


def scripted_demo(backends):
    failures = []

    heading("1. Two backends behind one proxy: requests take turns")
    answers = show_requests()
    check(failures, served_by(answers) == set(BACKEND_PORTS), "both backends served traffic")

    heading("2. Stopping the server on port 9002")
    backends[9002].terminate()
    backends[9002].wait()
    print("  (waiting for the proxy's health check to notice...)")
    time.sleep(4)
    answers = show_requests()
    check(failures, served_by(answers) == {9001}, "every request was still answered, all by 9001")

    heading("3. Starting port 9002 again")
    backends[9002] = start("server.py", "--port", "9002")
    wait_until_open(9002)
    time.sleep(4)
    answers = show_requests()
    check(failures, served_by(answers) == set(BACKEND_PORTS), "9002 rejoined without restarting the proxy")

    return failures


def main():
    parser = argparse.ArgumentParser(description="Run the load balancer demo with one command.")
    parser.add_argument(
        "--serve",
        action="store_true",
        help="start everything and keep it running so you can try it by hand",
    )
    args = parser.parse_args()

    busy = [p for p in [PROXY_PORT, *BACKEND_PORTS] if port_is_open(p)]
    if busy:
        print(f"Ports already in use: {busy}. Stop any running servers first.")
        sys.exit(1)

    backends = {}
    proxy = None
    failures = []
    try:
        print("Starting 2 backends and the proxy...")
        for port in BACKEND_PORTS:
            backends[port] = start("server.py", "--port", str(port))
        for port in BACKEND_PORTS:
            wait_until_open(port)
        proxy = start("proxy.py", "--port", str(PROXY_PORT), quiet=False)
        wait_until_open(PROXY_PORT)
        time.sleep(1)

        if args.serve:
            print(f"\nTry it: http://{HOST}:{PROXY_PORT}/whoami   (Ctrl+C to stop)")
            while True:
                time.sleep(1)
        else:
            failures = scripted_demo(backends)
    except KeyboardInterrupt:
        print("\nInterrupted.")
    finally:
        for process in [proxy, *backends.values()]:
            if process is not None and process.poll() is None:
                process.terminate()
                process.wait()
        print("\nEverything stopped.")

    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()