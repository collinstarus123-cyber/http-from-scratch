import socket
import sys
import threading
import time

HOST, PORT = "127.0.0.1", 8080
REQUEST = b"GET /about HTTP/1.1\r\nHost: x\r\n\r\n"


def one_request():
    start = time.perf_counter()
    with socket.create_connection((HOST, PORT), timeout=5) as s:
        s.sendall(REQUEST)
        while s.recv(4096):
            pass
    return time.perf_counter() - start


def worker(count, latencies, errors):
    for _ in range(count):
        try:
            latencies.append(one_request())
        except OSError:
            errors.append(1)


def run(clients, per_client):
    latencies, errors = [], []
    threads = [
        threading.Thread(target=worker, args=(per_client, latencies, errors))
        for _ in range(clients)
    ]

    start = time.perf_counter()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    elapsed = time.perf_counter() - start

    latencies.sort()
    done = len(latencies)
    print(f"Clients:            {clients} at the same time")
    print(f"Requests completed: {done}")
    print(f"Errors:             {len(errors)}")
    print(f"Total time:         {elapsed:.2f} s")
    if done:
        print(f"Requests/second:    {done / elapsed:.0f}")
        print(f"Average latency:    {sum(latencies) / done * 1000:.1f} ms")
        print(f"95th percentile:    {latencies[int(done * 0.95) - 1] * 1000:.1f} ms")


if __name__ == "__main__":
    try:
        socket.create_connection((HOST, PORT), timeout=2).close()
    except OSError:
        print("Cannot reach the server. Start it first with: python server.py")
        sys.exit(1)

    clients = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    per_client = int(sys.argv[2]) if len(sys.argv) > 2 else 200
    run(clients, per_client)