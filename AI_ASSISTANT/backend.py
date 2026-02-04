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

    def generate_response(self, user_input):
        # Wrap prompt with system instructions
        system_instruction = (
            f"User input: \"{user_input}\"\n"
            "Instructions: Answer in character as an anime assistant. Keep it brief (max 3 sentences). "
            "ONLY if the input/situation strongly calls for an emotion (like if you are insulted, embarrassed, or sad), "
            "append one of these tags: ~~expression:angry, ~~expression:sad, ~~expression:sweat, ~~expression:blush. "
            "DO NOT use a tag for normal conversation (like 'hello' or questions). "
            "Example: 'I-I'm not blushing! ~~expression:blush'"
        )
        
        self.history.append({"role": "user", "content": system_instruction})
        
        try:
            response_text = ""
            if self.model_type == "ollama":
                response = ollama.chat(model=self.ollama_model, messages=self.history)
                response_text = response['message']['content']
            
            elif self.model_type == "gemini":
                if not self.gemini_api_key:
                    return "Error: Gemini API Key not set."
                model = genai.GenerativeModel('gemini-pro')
                chat = model.start_chat(history=[]) 
                response = chat.send_message(system_instruction)
                response_text = response.text

            self.history.append({"role": "assistant", "content": response_text})
            return response_text

        except Exception as e:
            return f"Error connecting to AI: {str(e)}"

    def clear_history(self):
        self.history = []
