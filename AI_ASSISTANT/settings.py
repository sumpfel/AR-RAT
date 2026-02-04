from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QLineEdit, QComboBox, QPushButton, QFormLayout)
import json
import os

SETTINGS_FILE = "settings.json"

class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setFixedWidth(400)
        
        self.layout = QVBoxLayout(self)
        self.form_layout = QFormLayout()
        
        self.model_type = QComboBox()
        self.model_type.addItems(["ollama", "gemini"])
        self.form_layout.addRow("AI Model:", self.model_type)
        
        self.gemini_key = QLineEdit()
        self.gemini_key.setPlaceholderText("Enter Gemini API Key")
        self.gemini_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.form_layout.addRow("Gemini API Key:", self.gemini_key)
        
        self.ollama_model = QLineEdit()
        self.ollama_model.setText("llama3")
        self.form_layout.addRow("Ollama Model:", self.ollama_model)
        
        self.voice_name = QLineEdit()
        self.voice_name.setText("en-US-AriaNeural") 
        self.form_layout.addRow("Voice (edge-tts):", self.voice_name)

        self.layout.addLayout(self.form_layout)
        
        # Buttons
        btn_layout = QHBoxLayout()
        self.save_btn = QPushButton("Save")
        self.save_btn.clicked.connect(self.save_settings)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addWidget(self.save_btn)
        btn_layout.addWidget(self.cancel_btn)
        self.layout.addLayout(btn_layout)
        
        self.load_settings()

    def load_settings(self):
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, "r") as f:
                    data = json.load(f)
                    self.model_type.setCurrentText(data.get("model_type", "ollama"))
                    self.gemini_key.setText(data.get("gemini_key", ""))
                    self.ollama_model.setText(data.get("ollama_model", "llama3"))
                    self.voice_name.setText(data.get("voice", "en-US-AriaNeural"))
            except Exception as e:
                print(f"Error loading settings: {e}")

    def save_settings(self):
        data = {
            "model_type": self.model_type.currentText(),
            "gemini_key": self.gemini_key.text(),
            "ollama_model": self.ollama_model.text(),
            "voice": self.voice_name.text()
        }
        try:
            with open(SETTINGS_FILE, "w") as f:
                json.dump(data, f)
        except Exception as e:
            print(f"Error saving settings: {e}")
        self.accept()

    def get_settings(self):
        # Helper to read without UI
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, "r") as f:
                    return json.load(f)
            except:
                pass
        return {
            "model_type": "ollama", 
            "gemini_key": "", 
            "ollama_model": "llama3",
            "voice": "en-US-AriaNeural"
        }
