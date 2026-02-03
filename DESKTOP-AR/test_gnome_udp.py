import socket
import json
import time

UDP_IP = "127.0.0.1"
UDP_PORT = 5005

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

def send_cmd(cmd):
    msg = json.dumps({"cmd": cmd}).encode('utf-8')
    sock.sendto(msg, (UDP_IP, UDP_PORT))
    print(f"Sent: {cmd}")

print("Controls:")
print(" [n] Next Window")
print(" [p] Previous Window")
print(" [q] Quit")

while True:
    key = input("Command: ").strip()
    if key == 'n':
        send_cmd("focus_next")
    elif key == 'p':
        send_cmd("focus_prev")
    elif key == 'q':
        break
