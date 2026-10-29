import socket

s = socket.create_connection(("127.0.0.1", 8080))
s.sendall(b"this is not http\r\n\r\n")
print(s.recv(1024))