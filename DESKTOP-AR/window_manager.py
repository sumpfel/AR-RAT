import math

class Window:
    def __init__(self, win_id, yaw, pitch, width, height, color=(1.0, 1.0, 1.0), title="Window"):
        self.id = win_id
        # Coordinates in Degrees
        self.yaw = yaw      # Horizontal position (0 to 360)
        self.pitch = pitch  # Vertical position (-90 to 90)
        self.width = width  # Width in degrees
        self.height = height # Height in degrees
        self.color = color
        self.title = title

class WindowManager:
    def __init__(self):
        self.windows = []
        self.focused_window_idx = -1
        
        # Add some initial windows
        self.add_window(0, 0, 0, 40, 30, (1.0, 0.0, 0.0), "Main")
        self.add_window(1, 45, 0, 30, 20, (0.0, 1.0, 0.0), "Side")
        self.add_window(2, -45, 0, 30, 20, (0.0, 0.0, 1.0), "Docs")
        self.add_window(3, 0, 35, 40, 20, (1.0, 1.0, 0.0), "Top")

        self.focus_window(0)

    def add_window(self, win_id, yaw, pitch, w, h, color, title):
        self.windows.append(Window(win_id, yaw, pitch, w, h, color, title))

    def get_focused_window(self):
        if 0 <= self.focused_window_idx < len(self.windows):
            return self.windows[self.focused_window_idx]
        return None

    def focus_window(self, idx):
        if 0 <= idx < len(self.windows):
            self.focused_window_idx = idx
            print(f"Focused window: {self.windows[idx].title}")

    def move_focus(self, direction):
        if not self.windows:
            return

        current = self.get_focused_window()
        if not current:
            return

        best_candidate = -1
        best_dist = 999999

        # Simple heuristic to find nearest window in direction
        for i, win in enumerate(self.windows):
            if i == self.focused_window_idx:
                continue

            dyaw = (win.yaw - current.yaw + 180) % 360 - 180 # Shortest angular distance
            dpitch = win.pitch - current.pitch
            
            valid = False
            dist = math.sqrt(dyaw*dyaw + dpitch*dpitch)

            if direction == "left" and dyaw < -5:
                 if abs(dpitch) < 30: valid = True
            elif direction == "right" and dyaw > 5:
                 if abs(dpitch) < 30: valid = True
            elif direction == "up" and dpitch > 5:
                 if abs(dyaw) < 30: valid = True
            elif direction == "down" and dpitch < -5:
                 if abs(dyaw) < 30: valid = True

            if valid and dist < best_dist:
                best_dist = dist
                best_candidate = i
        
        if best_candidate != -1:
            self.focus_window(best_candidate)

    def move_current_window(self, dx, dy):
        win = self.get_focused_window()
        if win:
            win.yaw += dx
            win.pitch += dy

    def resize_current_window(self, dw, dh):
        win = self.get_focused_window()
        if win:
            win.width = max(10, win.width + dw)
            win.height = max(10, win.height + dh)
