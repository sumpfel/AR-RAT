import speech_recognition as sr
import edge_tts
import asyncio
import os
import tempfile
import threading

class AudioHandler:
    def __init__(self):
        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone()
        self.voice_output_file = os.path.join(tempfile.gettempdir(), "ai_assist_output.mp3")

    def listen(self):
        """
        Listens to microphone input and converts to text.
        """
        try:
            with self.microphone as source:
                self.recognizer.adjust_for_ambient_noise(source)
                print("Listening...")
                audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=10)
            
            print("Recognizing...")
            text = self.recognizer.recognize_google(audio)
            return text
        except Exception as e:
            print(f"Error listening: {e}")
            return ""

    async def _generate_speech(self, text, voice="en-US-AriaNeural"):
        communicate = edge_tts.Communicate(text, voice)
        if os.path.exists(self.voice_output_file):
            try:
                os.remove(self.voice_output_file)
            except:
                pass
        await communicate.save(self.voice_output_file)

    def generate_speech_file(self, text, voice="en-US-AriaNeural", callback=None):
        """
        Generates the speech file and calls callback with the path when done.
        """
        def run_gen():
            try:
                asyncio.run(self._generate_speech(text, voice))
                if callback:
                    callback(self.voice_output_file)
            except Exception as e:
                print(f"TTS Error: {e}")
                if callback:
                    callback(None)
        
        thread = threading.Thread(target=run_gen)
        thread.start()
