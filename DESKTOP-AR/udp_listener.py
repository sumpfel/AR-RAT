import socket
import threading
import json
import queue

class UDPListener:
    def __init__(self, port=5005):
        self.port = port
        self.running = True
        self.command_queue = queue.Queue()
        self.thread = threading.Thread(target=self._listen)
        self.thread.daemon = True
        
    def start(self):
        self.thread.start()
        
    def stop(self):
        self.running = False
        
    def _listen(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(("0.0.0.0", self.port))
        sock.settimeout(1.0)
        print(f"Listening for UDP commands on port {self.port}...")
        
        while self.running:
            try:
                data, addr = sock.recvfrom(1024)
                try:
                    msg = json.loads(data.decode('utf-8'))
                    self.command_queue.put(msg)
                    print(f"Received command: {msg}")
                except json.JSONDecodeError:
                    print(f"Invalid JSON from {addr}")
            except socket.timeout:
                continue
            except Exception as e:
                print(f"UDP Error: {e}")
                
    def get_command(self):
        try:
            return self.command_queue.get_nowait()
        except queue.Empty:
            return None
