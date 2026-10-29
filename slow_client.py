import socket
import time

s = socket.create_connection(("127.0.0.1", 8080))
print("Connected. Staying silent for 20 seconds...")
time.sleep(20)
s.close()
print("Gone.")