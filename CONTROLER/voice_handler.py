import speech_recognition as sr
import subprocess
import threading
import time
import re
import os
import sys
from contextlib import contextmanager
import ctypes

DEBUG_MODE = False

ERROR_HANDLER_FUNC = ctypes.CFUNCTYPE(None, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p)

def py_error_handler(filename, line, function, err, fmt):
    pass

c_error_handler = ERROR_HANDLER_FUNC(py_error_handler)

@contextmanager
def no_alsa_error():
    if DEBUG_MODE:
        yield
        return
        
    asound = ctypes.cdll.LoadLibrary('libasound.so')
    asound.snd_lib_error_set_handler(c_error_handler)
    yield
    asound.snd_lib_error_set_handler(None)

class VoiceHandler:
    def __init__(self, callback=None):
        self.recognizer = sr.Recognizer()
        self.callback = callback
        self.running = False
        self.thread = None
        self.trigger_word = "bash"
        
        # Suppress ALSA Error flood during init
        try:
            with no_alsa_error():
                self.microphone = sr.Microphone()
                with self.microphone as source:
                    self.recognizer.adjust_for_ambient_noise(source)
        except Exception as e:
            print(f"Mic Init Error: {e}")
            self.microphone = None

    def start(self):
        if self.running: return
        self.running = True
        self.thread = threading.Thread(target=self.listen_loop)
        self.thread.daemon = True
        self.thread.start()
        print("Voice Handler Started. Say 'Bash [command]'...")

    def stop(self):
        self.running = False
        if self.thread:
             self.thread.join(timeout=1)
        print("Voice Handler Stopped.")

    def listen_loop(self):
        if not self.microphone:
            print("No Microphone detected/initialized.")
            return
            
        while self.running:
            try:
                with no_alsa_error():
                    with self.microphone as source:
                        # Listen for phrase
                        audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=10)
                
                # Recognize
                try:
                    text = self.recognizer.recognize_google(audio).lower()
                    print(f"Heard: {text}")
                    self.process_command(text)
                        
                except sr.UnknownValueError:
                    pass # Could not understand
                except sr.RequestError as e:
                    print(f"Could not request results; {e}")
                    
            except Exception as e:
                # print(f"Voice Error: {e}")
                pass
            
            time.sleep(0.1)

    def process_command(self, text):
        # 0. Check for "STOP" / "CLOSE" / "CANCEL" (High Priority)
        # These should override everything?
        # Let's pass raw text to controller for state-based logic, 
        # BUT we also want to parse commands.
        
        # 1. Sanitize
        replacements = {
            "tilde": "~",
            "slash": "/",
            "backslash": "\\",
            "dash": "-",
            "space": " ",
            "dot": ".",
            "underscore": "_"
        }
        for word, char in replacements.items():
            text = text.replace(word, char)
            
        print(f"Heard cleaned: '{text}'")
        
        # 2. Logic
        # We emit event dicts to the controller
        
        # Check Trigger
        if self.trigger_word in text:
            # "bash list files"
            try:
                cmd_text = text.split(self.trigger_word, 1)[1].strip()
                if cmd_text:
                     if self.callback: self.callback({"type": "command_request", "cmd": cmd_text})
                     return
            except: pass
            
        # If not a command, maybe a keyword?
        # Just send raw text event, Controller decides if it matches "Eagle" or "Stop"
        if self.callback: self.callback({"type": "text", "text": text})

    def set_trigger(self, word):
        self.trigger_word = word.lower()
        print(f"Voice Trigger set to: {self.trigger_word}")

if __name__ == "__main__":
    v = VoiceHandler()
    v.start()
    while True:
        time.sleep(1)
