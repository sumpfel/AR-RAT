import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

class VirtualKeyboard:
    def __init__(self):
        self.keys = []
        self.layout_mode = "default" # default, symbols, emojis
        self.key_size = 60
        self.spacing = 10
        self.start_x = 50
        self.start_y = 100
        
        # Layouts
        self.char_layouts = {
            "default": [
                "QWERTYUIOP",
                "ASDFGHJKL",
                "ZXCVBNM"
            ],
            "symbols": [
                "1234567890",
                "@#$%&*-+=?",
                "!()[]{}<>"
            ],
            "emojis": [
                "😀😁😂🤣😃😄😅",
                "😉😊😋😎😍😘🥰",
                "😐😑😶🙄😏😣😥" 
            ]
        }
        
        self._refresh_keys()

    def _refresh_keys(self):
        self.keys = []
        y = self.start_y
        
        current_rows = self.char_layouts.get(self.layout_mode, self.char_layouts["default"])
        
        for row_idx, row in enumerate(current_rows):
            x = self.start_x + (row_idx * 30)
            for char in row:
                self.keys.append({
                    "char": char,
                    "x": x,
                    "y": y,
                    "w": self.key_size,
                    "h": self.key_size,
                    "type": "char"
                })
                x += self.key_size + self.spacing
            y += self.key_size + self.spacing
            
        # Functional Row
        x = self.start_x
        func_keys = [
            {"label": "DEL", "key": "BACKSPACE", "w": 80},
            {"label": "ENTER", "key": "ENTER", "w": 100},
            {"label": "SPACE", "key": "SPACE", "w": 200},
            {"label": "?123", "key": "SWITCH_LAYOUT_SYM", "w": 80},
            {"label": "😊", "key": "SWITCH_LAYOUT_EMO", "w": 60},
            {"label": "TAB", "key": "TAB", "w": 60}
        ]
        
        for k in func_keys:
            self.keys.append({
                "char": k["label"], # Display text
                "value": k["key"],  # Logical key
                "x": x,
                "y": y,
                "w": k["w"],
                "h": self.key_size,
                "type": "func"
            })
            x += k["w"] + self.spacing

    def draw(self, frame, active_key=None):
        """Draws the keyboard on the frame using PIL for Unicode support."""
        # Convert to PIL Image
        img_pil = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(img_pil, 'RGBA')
        
        # Load a font - try to find a system font that supports emojis if possible
        # Linux usually has Noto Color Emoji or similar, but complex to load in PIL correctly for colors.
        # Simple PIL load_default() doesn't support emojis well.
        # We need a TTF. Probing common paths.
        try:
            # Try DejaVuSans or NotoSans
            font = ImageFont.truetype("DejaVuSans.ttf", 20)
            # Emoji font?
            emoji_font = ImageFont.truetype("NotoColorEmoji.ttf", 20) # Often available on Linux
        except:
             font = ImageFont.load_default()
             emoji_font = font

        for key in self.keys:
            x, y, w, h = key["x"], key["y"], key["w"], key["h"]
            
            # Check active
            is_active = False
            key_val = key.get("value", key["char"])
            if active_key == key_val:
                is_active = True
                
            if is_active:
                fill_color = (0, 255, 0, 150) # RGBA
                outline_color = (0, 255, 0, 255)
            else:
                fill_color = (50, 50, 50, 150)
                outline_color = (255, 255, 255, 200)
            
            # Draw Box
            draw.rectangle([x, y, x + w, y + h], fill=fill_color, outline=outline_color, width=2)
            
            # Draw Text
            char = key["char"]
            
            # Measure text (basic centering)
            # PIL text centering is manual
            # For simplicity, just offset
            text_x = x + 10
            text_y = y + 15
            
            # Use emoji font if it looks like an emoji (len 1 and high codepoint, roughly)
            use_font = font
            if len(char) == 1 and ord(char) > 1000:
                 # It's likely an emoji or symbol
                 # Note: PIL default font won't render emojis. 
                 pass
            
            draw.text((text_x, text_y), char, font=use_font, fill=(255, 255, 255, 255))
            
        # Convert back to BGR/OpenCV
        frame[:] = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)

    def get_key_at(self, x, y):
        """Returns the logical key value at x,y."""
        for key in self.keys:
            kx, ky, kw, kh = key["x"], key["y"], key["w"], key["h"]
            if kx < x < kx + kw and ky < y < ky + kh:
                return key.get("value", key["char"])
        return None
        
    def switch_layout(self, target=None):
        if target:
            self.layout_mode = target
        else:
             # Cycle default -> symbols -> default
            if self.layout_mode == "default":
                self.layout_mode = "symbols"
            else:
                self.layout_mode = "default"
        self._refresh_keys()
