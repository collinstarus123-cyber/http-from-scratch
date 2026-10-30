import socket
import sys
import threading

HOST = "127.0.0.1"
PORT = 8080


def make_response(status, body):
    body_bytes = body.encode()
    return (
        f"HTTP/1.1 {status}\r\n"
        "Content-Type: text/plain\r\n"
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


def route(path, headers):
    if path == "/":
        return "200 OK", "Welcome to my server!"
    elif path == "/about":
        return "200 OK", "I built this server myself, from scratch."
    elif path == "/headers":
        body = "\n".join(f"{name}: {value}" for name, value in headers.items())
        return "200 OK", body
    else:
        return "404 Not Found", "Page not found"


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
        status, body = route(path, headers)
        conn.sendall(make_response(status, body))
    except Exception as error:
        print("Error handling request:", error)
    finally:
        conn.close()


def main():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    if sys.platform != "win32":
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen()
    server.settimeout(1)
    print("Server is running at http://127.0.0.1:8080")

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