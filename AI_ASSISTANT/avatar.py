from PyQt6.QtWidgets import QLabel, QWidget, QVBoxLayout
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QMovie
import os

class AvatarWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        self.label = QLabel(self)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.label)
        
        self.current_movie = None
        self.state_files = {
            "idle": "assets/idle.gif",
            "talking": "assets/talking.gif",
            "listening": "assets/listening.gif"
        }
        
        # Ensure assets directory exists
        if not os.path.exists("assets"):
            os.makedirs("assets")

    def set_state(self, state):
        file_path = self.state_files.get(state)
        if not file_path or not os.path.exists(file_path):
            self.label.setText(f"[{state.upper()}]")
            if self.current_movie:
                self.current_movie.stop()
                self.current_movie = None
            return

        if self.current_movie:
            self.current_movie.stop()
        
        self.current_movie = QMovie(file_path)
        self.current_movie.setScaledSize(QSize(300, 300)) # Adjust as needed
        self.label.setMovie(self.current_movie)
        self.current_movie.start()

    def set_file_for_state(self, state, filepath):
        self.state_files[state] = filepath
