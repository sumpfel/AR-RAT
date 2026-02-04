import google.generativeai as genai
import ollama

class AIBackend:
    def __init__(self):
        self.model_type = "ollama"  # or "gemini"
        self.ollama_model = "llama3" # Default ollama model
        self.gemini_api_key = ""
        self.history = []

    def set_mode(self, mode, **kwargs):
        self.model_type = mode
        if mode == "gemini":
            self.gemini_api_key = kwargs.get("api_key", "")
            if self.gemini_api_key:
                genai.configure(api_key=self.gemini_api_key)
        elif mode == "ollama":
            self.ollama_model = kwargs.get("model", "llama3")

    def generate_response(self, prompt):
        self.history.append({"role": "user", "content": prompt})
        
        try:
            response_text = ""
            if self.model_type == "ollama":
                response = ollama.chat(model=self.ollama_model, messages=self.history)
                response_text = response['message']['content']
            
            elif self.model_type == "gemini":
                if not self.gemini_api_key:
                    return "Error: Gemini API Key not set."
                model = genai.GenerativeModel('gemini-pro')
                # Gemini doesn't use the exact same history format as Ollama simple chat, 
                # but for single turn or simple context we can adapt. 
                # For now, let's just send the prompt or build a simple context string.
                # A robust implementation would map history to Gemini's format.
                chat = model.start_chat(history=[]) # complex history mapping skipped for MVP
                response = chat.send_message(prompt)
                response_text = response.text

            self.history.append({"role": "assistant", "content": response_text})
            return response_text

        except Exception as e:
            return f"Error connecting to AI: {str(e)}"

    def clear_history(self):
        self.history = []
