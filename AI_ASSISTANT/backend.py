import google.generativeai as genai
import ollama

class AIBackend:
    def __init__(self):
        self.model_type = "ollama"  # or "gemini"
        self.ollama_model = "llama3" # Default ollama model
        self.gemini_api_key = ""
        self.history = []

        self.anime_mode = True # Default
        
    def set_mode(self, mode, **kwargs):
        self.model_type = mode
        self.anime_mode = kwargs.get("anime_mode", True)
        
        if mode == "gemini":
            self.gemini_api_key = kwargs.get("api_key", "")
            if self.gemini_api_key:
                genai.configure(api_key=self.gemini_api_key)
        elif mode == "ollama":
            self.ollama_model = kwargs.get("model", "llama3")

    def generate_response(self, user_input):
        
        if self.anime_mode:
            # Anime Persona Prompt
            system_instruction = (
                f"User said: \"{user_input}\"\n"
                "Roleplay as an anime character assistant.\n"
                "Keep answers short (max 2 sentences).\n"
                "You MUST use an expression if the context fits even slightly. DO NOT BE SHY.\n"
                "Available tags: ~~expression:angry, ~~expression:sad, ~~expression:sweat, ~~expression:blush.\n"
                "Examples:\n"
                " 'That's mean! ~~expression:angry'\n"
                " 'Oh my... ~~expression:blush'\n"
                " 'I don't know what to do. ~~expression:sweat'\n"
                " 'I really hate this! ~~expression:angry'\n"
                "Answer now:"
            )
        else:
            # Normal Assistant Prompt
            system_instruction = (
                f"User said: \"{user_input}\"\n"
                "You are a helpful, concise AI assistant.\n"
                "Provide direct and short answers (max 2 sentences).\n"
                "Do not use any roleplay or emotional tags.\n"
                "Answer now:"
            )
        
        # Note: We append this to history as a new "user" message for simplicity in this MVP.
        # Ideally we'd set a system message once, but this works for single-turn robustness.
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
