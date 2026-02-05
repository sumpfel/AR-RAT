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
        import time
        t = int(time.time() * 1000)
        output_file = os.path.join(tempfile.gettempdir(), f"ai_assist_output_{t}.mp3")
        
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(output_file)
        return output_file

    def generate_speech_file(self, text, voice="en-US-AriaNeural", callback=None):
        """
        Generates the speech file and calls callback with the path when done.
        """
        def run_gen():
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                output_file = loop.run_until_complete(self._generate_speech(text, voice))
                loop.close()
                
                if callback:
                    callback(output_file)
            except Exception as e:
                print(f"TTS Error: {e}")
                if callback:
                    callback(None)
        
        thread = threading.Thread(target=run_gen)
        thread.start()
