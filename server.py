import socket

HOST = "127.0.0.1"
PORT = 8080

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind((HOST, PORT))
server.listen()
print("Server is running at http://127.0.0.1:8080")

while True:
    conn, addr = server.accept()
    data = conn.recv(4096)

    if not data:
        conn.close()
        continue

    text = data.decode()
    first_line = text.split("\r\n")[0]
    method, path, version = first_line.split(" ")

    print("Method :", method)
    print("Path   :", path)
    print("Version:", version)
    print("-----")

    if path == "/":
        status = "200 OK"
        body = "Welcome to my server!"
    elif path == "/about":
        status = "200 OK"
        body = "I built this server myself, from scratch."
    else:
        status = "404 Not Found"
        body = "Page not found"

    body_bytes = body.encode()
    reply = (
        f"HTTP/1.1 {status}\r\n"
        "Content-Type: text/plain\r\n"
        f"Content-Length: {len(body_bytes)}\r\n"
        "\r\n"
    ).encode() + body_bytes

    conn.sendall(reply)
    conn.close()