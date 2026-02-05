from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLineEdit, QPushButton, QLabel, QApplication, QFrame, QFileDialog, QTextEdit)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QUrl, QTimer, QPoint, QRect, QPointF, QRectF
from PyQt6.QtGui import QColor, QPalette, QCursor, QPainter, QPainterPath, QPen, QFont, QBrush, QTextDocument, QTextOption
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
import sys
import os
import re
import math
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
        self.is_thinking = False
        self.target_point = None 
        # We don't use QLabel anymore for complex scaling
        self.setSizePolicy(
            sys.modules['PyQt6.QtWidgets'].QSizePolicy.Policy.Expanding,
            sys.modules['PyQt6.QtWidgets'].QSizePolicy.Policy.Expanding
        )

    def setText(self, text, thinking=False):
        self.text = text
        self.is_thinking = thinking
        self.update()
        self.setVisible(True)

    def setTargetPoint(self, point):
        if point:
            self.target_point = self.mapFromGlobal(point)
            self.update()

    def paintEvent(self, event):
        if not self.text: return
        
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        
        w = self.width()
        h = self.height()
        
        # Define the bubble area
        # Leave minimal margin for the tail
        margin = 2
        bubble_rect = QRectF(margin, margin, w - 2*margin, h - 2*margin)
        
        # Dont let it be too flat
        if bubble_rect.height() < 50: bubble_rect.setHeight(50)
        
        painter.setPen(QPen(QColor("black"), 2))
        painter.setBrush(QColor("white"))

        path = QPainterPath()
        
        if self.is_thinking:
            # FLUFFY CLOUD (THINK BUBBLE)
            rx = bubble_rect.x()
            ry = bubble_rect.y()
            rw = bubble_rect.width()
            rh = bubble_rect.height()
            
            # Draw cloud shape using multiple overlapping ellipses
            # Main body
            path.addEllipse(rx, ry, rw, rh)
            
            # Randomize bumps for a more organic look (fixed seed for stability if needed, but pseudo-random is fine here)
            # Top bumps
            path.addEllipse(rx + rw*0.1, ry - rh*0.1, rw*0.3, rh*0.3)
            path.addEllipse(rx + rw*0.4, ry - rh*0.15, rw*0.3, rh*0.3)
            path.addEllipse(rx + rw*0.7, ry - rh*0.1, rw*0.3, rh*0.3)
            
            # Bottom bumps
            path.addEllipse(rx + rw*0.1, ry + rh*0.8, rw*0.3, rh*0.3)
            path.addEllipse(rx + rw*0.4, ry + rh*0.85, rw*0.3, rh*0.3)
            path.addEllipse(rx + rw*0.7, ry + rh*0.8, rw*0.3, rh*0.3)
            
            # Left bumps
            path.addEllipse(rx - rw*0.1, ry + rh*0.2, rw*0.3, rh*0.3)
            path.addEllipse(rx - rw*0.1, ry + rh*0.6, rw*0.3, rh*0.3)
            
            # Right bumps
            path.addEllipse(rx + rw*0.8, ry + rh*0.2, rw*0.3, rh*0.3)
            path.addEllipse(rx + rw*0.8, ry + rh*0.6, rw*0.3, rh*0.3)

            painter.drawPath(path)
            
            # Thinking Dots (Tail) pointing to target
            if self.target_point:
                start = QPointF(rx + rw*0.3, ry + rh) # Start from bottom-left-ish
                end = QPointF(self.target_point)
                
                # Draw 3 bubbles decreasing in size towards the head
                # But actually, think bubbles usually go: Small -> Medium -> Large Cloud
                # So from Head (Small) -> Cloud (Large)
                
                # Calculate vector
                dx = end.x() - start.x()
                dy = end.y() - start.y()
                dist = math.hypot(dx, dy)
                
                if dist > 20: 
                    # 3 bubbles
                    for i in range(3):
                        # 0 is near cloud, 2 is near head
                        t = (i + 1) / 4.0 
                        cx = start.x() + dx * t
                        cy = start.y() + dy * t
                        
                        r = 8 - i * 2 # 8, 6, 4
                        painter.drawEllipse(QPointF(cx, cy), r, r)

        else:
            # NORMAL OVAL BUBBLE
            path.addEllipse(bubble_rect)
            
            # Proper Speech Tail
            if self.target_point:
                target = QPointF(self.target_point)
                center = bubble_rect.center()
                
                # Compute direction
                dx = target.x() - center.x()
                dy = target.y() - center.y()
                
                # Find intersection with ellipse roughly
                # We'll just anchor at bottom or relevant side
                # For now, simplistic bottom anchor is usually okay for character above/below
                # But let's try to be smart.
                
                anchor_width = 30
                
                # Closest point on rect perimeter logic is complex, 
                # let's stick to bottom anchor if target is below, top if target is above
                if target.y() > bubble_rect.bottom():
                    # Target is below
                    anchor_x = center.x()
                    anchor_y = bubble_rect.bottom() - 5
                    
                    p1 = QPointF(anchor_x - 15, anchor_y)
                    p2 = QPointF(anchor_x + 15, anchor_y)
                    tip = target
                    
                    # Curved tail
                    tail_path = QPainterPath()
                    tail_path.moveTo(p1)
                    tail_path.quadTo(QPointF(anchor_x - 5, anchor_y + (tip.y()-anchor_y)*0.5), tip)
                    tail_path.quadTo(QPointF(anchor_x + 5, anchor_y + (tip.y()-anchor_y)*0.5), p2)
                    tail_path.closeSubpath()
                    
                    path = path.united(tail_path)
                
                elif target.y() < bubble_rect.top():
                   # Target is above (unlikely for assistant but possible)
                    anchor_x = center.x()
                    anchor_y = bubble_rect.top() + 5
                    
                    p1 = QPointF(anchor_x - 15, anchor_y)
                    p2 = QPointF(anchor_x + 15, anchor_y)
                    tip = target
                    
                    tail_path = QPainterPath()
                    tail_path.moveTo(p1)
                    tail_path.lineTo(tip)
                    tail_path.lineTo(p2)
                    tail_path.closeSubpath()
                    path = path.united(tail_path)

                else:
                    # Side?
                    pass # Keep simple oval if inside
            
            painter.drawPath(path)

        # Draw Text
        # Maximize text area within the ellipse
        # Ellipse inscribed rect is W/sqrt(2), H/sqrt(2) approx 0.707
        # We can push it a bit more
        text_rect_w = bubble_rect.width() * 0.85 
        text_rect_h = bubble_rect.height() * 0.80
        
        text_rect_x = bubble_rect.center().x() - text_rect_w / 2
        text_rect_y = bubble_rect.center().y() - text_rect_h / 2
        
        text_rect = QRectF(text_rect_x, text_rect_y, text_rect_w, text_rect_h)
        
        # Prepare Text
        display_text = self.text
        display_text = display_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        display_text = re.sub(r'\*([^\*]+)\*', r'<i>\1</i>', display_text)
        
        # Font Scaling
        font_size = 24 # Start bigger
        min_font = 9
        font_family = 'Brush Script MT' if self.is_thinking else 'Comic Sans MS'
        if self.is_thinking: font_size += 6
        
        doc = QTextDocument()
        opt = QTextOption()
        opt.setWrapMode(QTextOption.WrapMode.WordWrap)
        doc.setDefaultTextOption(opt)
        
        doc.setDefaultFont(QFont(font_family, font_size))
        doc.setHtml(f"<div align='center' style='line-height: 100%;'>{display_text}</div>")
        doc.setTextWidth(text_rect_w)
        
        while font_size > min_font:
            doc.setDefaultFont(QFont(font_family, font_size))
            # Check height
            if doc.size().height() <= text_rect_h:
                break
            font_size -= 1
        
        # Final set
        doc.setDefaultFont(QFont(font_family, font_size))
        doc.setHtml(f"<div align='center'>{display_text}</div>")
        doc.setTextWidth(text_rect_w)

        # Draw text centered
        painter.save()
        doc_h = doc.size().height()
        y_centering = max(0, (text_rect_h - doc_h) / 2)
        painter.translate(text_rect.x(), text_rect.y() + y_centering)
        doc.drawContents(painter)
        painter.restore()

class MainWindow(QMainWindow):
    audio_ready = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.audio_ready.connect(self._play_audio_slot)
        
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)
        self.player.mediaStatusChanged.connect(self.on_media_status_changed)

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setGeometry(100, 100, 400, 700) # Taller window to give space
        
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.central_layout = QVBoxLayout(self.central_widget)
        self.central_layout.setContentsMargins(0, 0, 0, 0)
        self.central_layout.setSpacing(0)
        
        # Bubble Container
        # Give it explicit size policy to expand
        self.bubble_container = QWidget()
        self.bubble_layout = QVBoxLayout(self.bubble_container)
        self.bubble_layout.setContentsMargins(0, 0, 0, 0)
        self.speech_bubble = MangaSpeechBubble("")
        self.bubble_layout.addWidget(self.speech_bubble)
        
        # Avatar
        self.avatar = AvatarWidget()
        self.avatar.mouthPositionChanged.connect(self.update_bubble_tail)
        
        # Controls
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
        self.controls_layout.setSpacing(8)
        
        # Buttons
        self.btn_layout = QHBoxLayout()
        self.btn_layout.setSpacing(8)
        
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
                    border-radius: 18px; 
                    color: #333;
                    font-size: 18px;
                }
                QPushButton:hover {
                    background-color: #e0e0e0;
                }
                QPushButton:checked {
                    background-color: #b0ffb0;
                    border-color: #4c4;
                }
            """)
            return btn

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
        
        # Layout Stretches
        # Increase bubble stretch to give it more room
        self.central_layout.addWidget(self.bubble_container, stretch=3)
        self.central_layout.addWidget(self.avatar, stretch=4)
        self.central_layout.addWidget(self.controls_frame, stretch=0)
        
        self.backend = AIBackend()
        self.audio = AudioHandler()
        self.settings = SettingsDialog().get_settings()
        self.update_backend_settings()
        
        self.is_muted = False
        self.old_pos = None

    def update_bubble_tail(self, mouth_pos_local):
        global_pos = self.avatar.mapToGlobal(mouth_pos_local)
        self.speech_bubble.setTargetPoint(global_pos)

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
            self.speech_bubble.setText("Tap mouth!", False)
            self.setCursor(Qt.CursorShape.CrossCursor)
        else:
            self.speech_bubble.setText("Saved!", False)
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def toggle_mute(self):
        self.is_muted = self.mute_btn.isChecked()
        self.mute_btn.setText("🔇" if self.is_muted else "🔊")
        if self.is_muted:
            self.player.stop()

    def toggle_voice(self):
        self.avatar.set_state("listening")
        self.speech_bubble.setText("Listening...", True)
        self.voice_worker = VoiceWorker(self.audio)
        self.voice_worker.text_ready.connect(self.on_voice_input)
        self.voice_worker.start()

    def on_voice_input(self, text):
        if text:
            self.input_field.setText(text)
            self.handle_input()
        else:
            self.speech_bubble.setText("...", True)
            self.avatar.set_state("idle")

    def handle_input(self):
        text = self.input_field.text()
        if not text:
            return
            
        self.input_field.clear()
        self.speech_bubble.setText("Thinking...", True)
        self.avatar.set_state("talking") 
        
        self.ai_worker = AIWorker(self.backend, text)
        self.ai_worker.finished.connect(self.on_ai_response)
        self.ai_worker.start()

    def on_ai_response(self, response):
        print(f"RAW RESP: {response}") 
        
        # Find all emotions, but use the last one for the avatar state
        emotions = re.findall(r'~~expression:(\w+)', response)
        emotion = emotions[-1].lower() if emotions else None
        
        # Clean the response of all emotion tags for display
        clean_response = re.sub(r'~~expression:\w+', '', response).strip()
        
        # TTS Text: remove *actions* and any leftover artifacts
        tts_text = re.sub(r'\*.*?\*', '', clean_response).strip()
        # If the user specifically wants the voice to match the text exactly (including *actions*), 
        # we would keep them. But usually, we strip them. 
        # However, I'll make sure it's not "different" in a buggy way.
        if not tts_text: tts_text = "..." 
            
        self.speech_bubble.setText(clean_response, False)
        
        if emotion:
            self.avatar.set_emotion(emotion)
        else:
            lower = response.lower()
            if any(x in lower for x in ["angry", "idiot", "stupid", "hate"]):
                self.avatar.set_emotion("angry")
            elif any(x in lower for x in ["sad", "sorry", "cry"]):
                self.avatar.set_emotion("sad")
            elif any(x in lower for x in ["sweat", "nervous", "uhm", "uhh"]):
                 self.avatar.set_emotion("sweat")
            elif any(x in lower for x in ["blush", "cute", "love", "like you", "wow", "great", "thank"]):
                 self.avatar.set_emotion("blush")
            elif any(x in lower for x in ["happy", "nice", "fun"]):
                 # Mapping happy to blush for now as a positive emotion
                 self.avatar.set_emotion("blush")
        
        if not self.is_muted:
            voice_name = self.settings.get("voice", "en-US-AriaNeural")
            self.audio.generate_speech_file(tts_text, voice=voice_name, callback=self.trigger_audio_playback)
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
