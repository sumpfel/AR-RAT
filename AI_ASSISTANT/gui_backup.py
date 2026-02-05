from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLineEdit, QPushButton, QLabel, QApplication, QFrame)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QUrl
from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
import sys
import os
from avatar import AvatarWidget
from audio import AudioHandler
from backend import AIBackend
from settings import SettingsDialog

class AIWorker(QThread):
    finished = pyqtSignal(str)
    
    def __init__(self, backend, prompt):
        super().__init__()
        self.backend = backend
        self.prompt = prompt
        
    def run(self):
        response = self.backend.generate_response(self.prompt)
        self.finished.emit(response)

class VoiceWorker(QThread):
    text_ready = pyqtSignal(str)
    
    def __init__(self, audio_handler):
        super().__init__()
        self.audio_handler = audio_handler
        
    def run(self):
        text = self.audio_handler.listen()
        self.text_ready.emit(text)

class MainWindow(QMainWindow):
    audio_ready = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.audio_ready.connect(self._play_audio_slot)
        
        # Audio Player Setup
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)
        self.player.mediaStatusChanged.connect(self.on_media_status_changed)

        # Transparent Window Setup
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setGeometry(100, 100, 400, 600)
        
        # Central Widget
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        
        # Avatar
        self.avatar = AvatarWidget()
        self.avatar.setFixedSize(300, 300)
        self.main_layout.addWidget(self.avatar, alignment=Qt.AlignmentFlag.AlignCenter)
        self.avatar.set_state("idle")
        
        # Text Bubble
        self.bubble = QLabel("Hi! I'm your assistant.")
        self.bubble.setWordWrap(True)
        self.bubble.setStyleSheet("""
            background-color: rgba(255, 255, 255, 200);
            border-radius: 10px;
            padding: 10px;
            color: black;
            font-size: 14px;
        """)
        self.main_layout.addWidget(self.bubble)
        
        # Controls Container
        self.controls_frame = QFrame()
        self.controls_frame.setStyleSheet("background-color: rgba(0, 0, 0, 150); border-radius: 10px;")
        self.controls_layout = QVBoxLayout(self.controls_frame)
        self.controls_layout.setContentsMargins(5, 5, 5, 5)
        
        # Buttons Setup
        self.btn_layout = QHBoxLayout()
        
        self.voice_btn = QPushButton("🎤")
        self.voice_btn.setFixedSize(30, 30)
        self.voice_btn.clicked.connect(self.toggle_voice)
        
        self.mute_btn = QPushButton("🔊")
        self.mute_btn.setFixedSize(30, 30)
        self.mute_btn.setCheckable(True)
        self.mute_btn.clicked.connect(self.toggle_mute)
        
        self.settings_btn = QPushButton("⚙️")
        self.settings_btn.setFixedSize(30, 30)
        self.settings_btn.clicked.connect(self.open_settings)

        self.close_btn = QPushButton("❌")
        self.close_btn.setFixedSize(30, 30)
        self.close_btn.clicked.connect(self.close)
        
        self.btn_layout.addWidget(self.voice_btn)
        self.btn_layout.addWidget(self.mute_btn)
        self.btn_layout.addWidget(self.settings_btn)
        self.btn_layout.addWidget(self.close_btn)
        self.btn_layout.addStretch()
        
        self.controls_layout.addLayout(self.btn_layout)
        
        # Text Input
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Type here...")
        self.input_field.returnPressed.connect(self.handle_input)
        self.input_field.setStyleSheet("""
            QLineEdit {
                border: 1px solid #555;
                border-radius: 5px;
                padding: 5px;
                background-color: white;
                color: black;
            }
        """)
        self.controls_layout.addWidget(self.input_field)
        
        self.main_layout.addWidget(self.controls_frame)
        
        # Backend & Audio
        self.backend = AIBackend()
        self.audio = AudioHandler()
        self.settings = SettingsDialog().get_settings()
        self.update_backend_settings()
        
        self.is_muted = False
        self.old_pos = None

    def update_backend_settings(self):
        self.settings = SettingsDialog().get_settings()
        self.backend.set_mode(
            self.settings["model_type"], 
            api_key=self.settings["gemini_key"],
            model=self.settings["ollama_model"]
        )

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.old_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if self.old_pos:
            delta = event.globalPosition().toPoint() - self.old_pos
            self.move(self.pos() + delta)
            self.old_pos = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event):
        self.old_pos = None

    def open_settings(self):
        dlg = SettingsDialog(self)
        if dlg.exec():
            self.update_backend_settings()

    def toggle_mute(self):
        self.is_muted = self.mute_btn.isChecked()
        self.mute_btn.setText("🔇" if self.is_muted else "🔊")
        if self.is_muted:
            self.player.stop()

    def toggle_voice(self):
        self.avatar.set_state("listening")
        self.bubble.setText("Listening...")
        self.voice_worker = VoiceWorker(self.audio)
        self.voice_worker.text_ready.connect(self.on_voice_input)
        self.voice_worker.start()

    def on_voice_input(self, text):
        if text:
            self.input_field.setText(text)
            self.handle_input()
        else:
            self.bubble.setText("Create didn't hear anything.")
            self.avatar.set_state("idle")

    def handle_input(self):
        text = self.input_field.text()
        if not text:
            return
            
        self.input_field.clear()
        self.bubble.setText("Thinking...")
        self.avatar.set_state("talking") 
        
        self.ai_worker = AIWorker(self.backend, text)
        self.ai_worker.finished.connect(self.on_ai_response)
        self.ai_worker.start()

    def on_ai_response(self, response):
        self.bubble.setText(response)
        
        if not self.is_muted:
            voice_name = self.settings.get("voice", "en-US-AriaNeural")
            self.audio.generate_speech_file(response, voice=voice_name, callback=self.trigger_audio_playback)
        else:
            self.avatar.set_state("idle")

    def trigger_audio_playback(self, file_path):
        self.audio_ready.emit(file_path)

    def _play_audio_slot(self, file_path):
        if file_path and os.path.exists(file_path):
             self.player.setSource(QUrl.fromLocalFile(file_path))
             self.player.play()
             self.avatar.set_state("talking")

    def on_media_status_changed(self, status):
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self.avatar.set_state("idle")
