import os
import math
import struct
import time
import threading

class SoundManager:
    def __init__(self, mode='none'):
        self.mode = mode
        self.enabled = mode in ['alarm', 'all']
        self.all_sounds = mode == 'all'
        
        self.next_alarm = 0
        self.next_ping = 0
        
        self.files_ready = False
        
        if self.enabled:
            # Generate WAV files in background
            t = threading.Thread(target=self.generate_files)
            t.daemon = True
            t.start()

    def generate_files(self):
        try:
            # Alarm: 880Hz, Square-ish, 0.2s - MAX VOLUME
            self.create_wav("alarm.wav", 880, 0.2, wave_type='square', volume=1.0)
            # Chirp: 1200Hz, Sine, 0.05s - MAX VOLUME
            self.create_wav("chirp.wav", 1200, 0.05, wave_type='sine', volume=1.0)
            self.files_ready = True
            print("Sound System: WAV files generated at MAX volume.")
        except Exception as e:
            print(f"Failed to generate WAVs: {e}")
            self.enabled = False

    def create_wav(self, filename, freq, duration, wave_type='sine', volume=0.5, sample_rate=44100):
        # Generate raw data
        n_samples = int(sample_rate * duration)
        data = []
        
        for i in range(n_samples):
            t = float(i) / sample_rate
            if wave_type == 'sine':
                val = math.sin(2 * math.pi * freq * t)
            else: # Square
                val = 1.0 if math.sin(2 * math.pi * freq * t) > 0 else -1.0
            
            # Scale and clip
            val = max(-1.0, min(1.0, val * volume))
            data.append(int(val * 32767))
            
        # Write WAV file
        with open(filename, 'wb') as f:
            # WAV Header
            f.write(b'RIFF')
            f.write(struct.pack('<I', 36 + n_samples * 2))
            f.write(b'WAVEfmt ')
            f.write(struct.pack('<IHHIIHH', 16, 1, 1, sample_rate, sample_rate * 2, 2, 16))
            f.write(b'data')
            f.write(struct.pack('<I', n_samples * 2))
            
            # Data
            for sample in data:
                f.write(struct.pack('<h', sample))

    def play(self, filename):
        if not self.enabled or not self.files_ready: return
        # Run aplay in background
        os.system(f"aplay -q {filename} &")

    def update(self, is_upside_down, target_count, best_detection=None):
        if not self.enabled: return
        
        now = time.time()
        
        # 1. UPSIDE DOWN ALARM (Priority)
        if is_upside_down:
            if now > self.next_alarm:
                self.play("alarm.wav")
                self.next_alarm = now + 0.4
            return
            
        # 2. TARGET SOUNDS
        if self.all_sounds and target_count > 0:
            if now > self.next_ping:
                self.play("chirp.wav")
                self.next_ping = now + 1.0
