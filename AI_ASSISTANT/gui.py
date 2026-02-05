from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLineEdit, QPushButton, QLabel, QApplication, QFrame, QFileDialog, QTextEdit)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QUrl, QTimer
from PyQt6.QtGui import QColor, QPalette, QCursor, QPainter, QPainterPath, QPen
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
import sys
import os
import re
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

class MangaSpeechBubble(QWidget):
    def __init__(self, text="", parent=None):
        super().__init__(parent)
        self.text = text
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        self.label = QLabel(self)
        self.label.setWordWrap(True)
        # Comic Sans like font for Manga feel?
        self.label.setStyleSheet("color: black; font-family: 'Comic Sans MS', sans-serif; font-size: 14px; background-color: transparent;")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(20, 15, 20, 25) # Padding for bubble + tail space
        self.layout.addWidget(self.label)
        self.setVisible(False)

    def setText(self, text):
        self.text = text
        self.label.setText(text)
        self.adjustSize()
        self.setVisible(True)

    def paintEvent(self, event):
        if not self.text: return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        path = QPainterPath()
        w = self.width()
        h = self.height() - 15 # Minus tail height
        r = 20 # roundedness
        
        # Elliptical / Rounded Rect Bubble
        path.addRoundedRect(1, 1, w-2, h, r, r)
        
        # Tail (Sharp manga style)
        path.moveTo(w // 2 - 15, h)
        path.lineTo(w // 2, h + 15)
        path.lineTo(w // 2 + 5, h)
        
        # Border
        painter.setPen(QPen(QColor("black"), 2))
        painter.setBrush(QColor("white"))
        painter.drawPath(path)

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

        # Transparent Window
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setGeometry(100, 100, 400, 600)
        
        # Central Widget
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.central_layout = QVBoxLayout(self.central_widget)
        self.central_layout.setContentsMargins(0, 0, 0, 0)
        self.central_layout.setSpacing(0)
        
        # Bubble Container
        self.bubble_container = QWidget()
        self.bubble_layout = QVBoxLayout(self.bubble_container)
        self.bubble_layout.setContentsMargins(20, 20, 20, 0)
        self.speech_bubble = MangaSpeechBubble("")
        self.bubble_layout.addWidget(self.speech_bubble)
        self.bubble_layout.addStretch()
        
        # Avatar (Takes most space)
        self.avatar = AvatarWidget()
        
        # Controls (Opaque Bar)
        self.controls_frame = QFrame()
        self.controls_frame.setStyleSheet("""
            QFrame {
                background-color: #f5f5f5; 
                border-top: 1px solid #999;
                border-top-left-radius: 10px;
                border-top-right-radius: 10px;
            }
        """)
        self.controls_layout = QVBoxLayout(self.controls_frame)
        self.controls_layout.setContentsMargins(10, 10, 10, 10)
        self.controls_layout.setSpacing(10)
        
        # -- Reverted Layout (Similar to original) --
        
        # Buttons Row
        self.btn_layout = QHBoxLayout()
        self.btn_layout.setSpacing(10)
        
        def create_btn(text, func, tooltip, checkable=False):
            btn = QPushButton(text)
            btn.setFixedSize(36, 36)
            btn.setToolTip(tooltip)
            if checkable:
                btn.setCheckable(True)
            btn.clicked.connect(func)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: white;
                    border: 1px solid #ccc;
                    border-radius: 18px; /* Circular */
                    color: #333;
                    font-size: 18px;
                }
                QPushButton:hover {
                    background-color: #e0e0e0;
                    border-color: #888;
                }
                QPushButton:checked {
                    background-color: #b0ffb0;
                    border-color: #4c4;
                }
            """)
            return btn

        # Order: Voice | Mute | Settings | Spacers | Upload | Calibrate | Close
        self.voice_btn = create_btn("🎤", self.toggle_voice, "Voice Input")
        self.mute_btn = create_btn("🔊", self.toggle_mute, "Mute TTS", True)
        self.settings_btn = create_btn("⚙️", self.open_settings, "Settings")
        
        self.upload_btn = create_btn("📁", self.upload_character, "Upload Character/Video")
        self.calibrate_btn = create_btn("👄", self.toggle_calibration, "Calibrate Mouth", True)
        self.close_btn = create_btn("❌", self.close, "Close")
        
        self.btn_layout.addWidget(self.voice_btn)
        self.btn_layout.addWidget(self.mute_btn)
        self.btn_layout.addWidget(self.settings_btn)
        self.btn_layout.addStretch()
        self.btn_layout.addWidget(self.upload_btn)
        self.btn_layout.addWidget(self.calibrate_btn)
        self.btn_layout.addWidget(self.close_btn)
        
        # Input Field
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Type a message...")
        self.input_field.returnPressed.connect(self.handle_input)
        self.input_field.setStyleSheet("""
            QLineEdit {
                border: 1px solid #ccc;
                border-radius: 20px;
                padding: 8px 15px;
                font-size: 14px;
                background-color: white;
                color: black;
            }
            QLineEdit:focus {
                border: 2px solid #aaa;
            }
        """)
        
        self.controls_layout.addLayout(self.btn_layout)
        self.controls_layout.addWidget(self.input_field)
        
        # Add widgets to central layout
        # Overlapping avatar and bubble is hard with pure QVBox without stacked layout, 
        # but to keep it simple we can stack them vertically or use parent geometry.
        # User wants bubble "like manga". Usually that's ABOVE head.
        
        self.central_layout.addWidget(self.bubble_container, stretch=1)
        self.central_layout.addWidget(self.avatar, stretch=4)
        self.central_layout.addWidget(self.controls_frame, stretch=0)
        
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
            if self.calibrate_btn.isChecked(): return
            
            # Allow dragging window if clicking on transparent areas (avatar/bubble area)
            # but not controls
            child = self.central_widget.childAt(event.position().toPoint())
            if not child or (child is not self.controls_frame and not self.controls_frame.isAncestorOf(child)):
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

    def upload_character(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Upload Character", "", "Images/Videos (*.png *.jpg *.jpeg *.mp4 *.webm *.gif)")
        if file_path:
            self.avatar.import_waifu(file_path)

    def toggle_calibration(self):
        is_active = self.avatar.toggle_calibration_mode()
        self.calibrate_btn.setChecked(is_active)
        if is_active:
            self.speech_bubble.setText("Tap mouth center!")
            self.setCursor(Qt.CursorShape.CrossCursor)
        else:
            self.speech_bubble.setText("Saved!")
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def toggle_mute(self):
        self.is_muted = self.mute_btn.isChecked()
        self.mute_btn.setText("🔇" if self.is_muted else "🔊")
        if self.is_muted:
            self.player.stop()

    def toggle_voice(self):
        self.avatar.set_state("listening")
        self.speech_bubble.setText("Listening...")
        self.voice_worker = VoiceWorker(self.audio)
        self.voice_worker.text_ready.connect(self.on_voice_input)
        self.voice_worker.start()

    def on_voice_input(self, text):
        if text:
            self.input_field.setText(text)
            self.handle_input()
        else:
            self.speech_bubble.setText("...")
            self.avatar.set_state("idle")

    def handle_input(self):
        text = self.input_field.text()
        if not text:
            return
            
        self.input_field.clear()
        self.speech_bubble.setText(" Thinking... ")
        self.avatar.set_state("talking") 
        
        self.ai_worker = AIWorker(self.backend, text)
        self.ai_worker.finished.connect(self.on_ai_response)
        self.ai_worker.start()

    def on_ai_response(self, response):
        # Parse Expression
        emotion = None
        clean_response = response
        
        match = re.search(r'~~expression:(\w+)', response)
        if match:
            emotion = match.group(1).lower()
            clean_response = response.replace(match.group(0), "").strip()
            
        self.speech_bubble.setText(clean_response)
        if emotion:
            self.avatar.set_emotion(emotion)
        
        if not self.is_muted:
            voice_name = self.settings.get("voice", "en-US-AriaNeural")
            self.audio.generate_speech_file(clean_response, voice=voice_name, callback=self.trigger_audio_playback)
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
