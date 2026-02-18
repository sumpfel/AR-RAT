import os
import config

# --- HARDWARE IMPORTS ---
try:
    import platform
    
    # helper to check if RPi
    def is_raspberry_pi():
        try:
            with open('/sys/firmware/devicetree/base/model', 'r') as m:
                if 'raspberry pi' in m.read().lower(): return True
        except Exception: pass
        return False

    # Check Config Mode
    should_try_ft232h = False
    
    if config.HARDWARE_MODE == "FT232H":
        should_try_ft232h = True
    elif config.HARDWARE_MODE == "AUTO":
        if not is_raspberry_pi():
             should_try_ft232h = True
    
    if should_try_ft232h:
        os.environ["BLINKA_FT232H"] = "1"
    elif config.HARDWARE_MODE == "RPI":
         if "BLINKA_FT232H" in os.environ: del os.environ["BLINKA_FT232H"]
    
    import board
    import digitalio
    import busio
    HAS_HARDWARE_LIBS = True
    
except (ImportError, RuntimeError) as e:
    # This catches the "BLINKA_FT232H set but no device" error
    print(f"[HardwareManager] Hardware Libs not found or error: {e}")
    HAS_HARDWARE_LIBS = False

# --- MOCK CLASSES ---
class MockPin:
    def __init__(self, name):
        self.name = name
        self.direction = None
        self.value = False # Default low (not pressed)

class MockI2C:
    def __init__(self): pass
    def try_lock(self): return True
    def unlock(self): pass
    def scan(self): return []

class HardwareManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(HardwareManager, cls).__new__(cls)
            cls._instance.initialized = False
        return cls._instance

    def __init__(self):
        if self.initialized: return
        self.initialized = True
        
        self.mode = "MOCK"
        self.i2c = None
        self.buttons = {}
        
        self._detect_hardware()
        print(f"[HardwareManager] Initialized in {self.mode} Mode")

    def _detect_hardware(self):
        if not HAS_HARDWARE_LIBS:
            self.mode = "MOCK"
            return

        # Attempt Detection
        try:
            board_id = getattr(board, 'board_id', 'Unknown')
            print(f"[HardwareManager] Board ID: {board_id}")
            
            if board_id == 'ft232h':
                 self.mode = "FT232H"
                 self.i2c = board.I2C()
                 self._update_config_pins('FT')
                 
            elif board_id in ['raspberry_pi_4b', 'raspberry_pi_5', 'raspberry_pi_3b', 'raspberry_pi_zero']:
                 self.mode = "RPI"
                 self.i2c = board.I2C()
                 self._update_config_pins('RPI')
            
            elif board_id == 'GENERIC_LINUX_PC':
                # This happens if we didn't set the env var, or if detection failed gracefully?
                # If we are here, it means we probably are in MOCK mode effectively for GPIO
                print("[HardwareManager] Start on Generic PC -> MOCK Mode")
                self.mode = "MOCK"
                self.i2c = MockI2C()
                
            else:
                # Fallback or Generic
                 print(f"[HardwareManager] Unrecognized Board: {board_id}")
                 # Try generic I2C
                 try:
                    self.i2c = board.I2C()
                    self.mode = "GENERIC"
                 except:
                    self.mode = "MOCK"
                 
        except Exception as e:
            print(f"[HardwareManager] Hardware Detection Failed: {e}")
            self.mode = "MOCK"
            self.i2c = MockI2C()

    def _update_config_pins(self, platform):
        # Update config module PIN constants to match platform
        if platform == 'RPI':
            config.PIN_C0 = config.RPI_BACK
            config.PIN_C1 = config.RPI_SELECT
            config.PIN_C2 = config.RPI_MENU
            config.PIN_C3 = config.RPI_DOWN
            config.PIN_D4 = config.RPI_UP
            config.PIN_C4 = config.RPI_LEFT
            config.PIN_C6 = config.RPI_RIGHT
        elif platform == 'FT':
            config.PIN_C0 = config.FT_BACK
            config.PIN_C1 = config.FT_SELECT
            config.PIN_C2 = config.FT_MENU
            config.PIN_C3 = config.FT_DOWN
            config.PIN_D4 = config.FT_UP
            config.PIN_C4 = config.FT_LEFT
            config.PIN_C6 = config.FT_RIGHT

    def get_i2c(self):
        if not self.i2c: return MockI2C()
        return self.i2c

    def setup_pin(self, pin_name, direction=None):
        if self.mode == "MOCK":
            return MockPin(pin_name)
            
        try:
            if direction is None: direction = digitalio.Direction.INPUT
            
            # Resolve Pin Object
            pin_obj = None
            
            # If RPI, pin_name is int (e.g. 17). We need board.D17
            if self.mode == "RPI":
                # Convert int to board.D{int}
                p_str = f"D{pin_name}"
                if hasattr(board, p_str):
                    pin_obj = getattr(board, p_str)
            else:
                # FT232H or Generic uses string names like "C0", "D4" directly usually
                if hasattr(board, pin_name):
                    pin_obj = getattr(board, pin_name)
            
            if not pin_obj:
                 print(f"[HardwareManager] Pin {pin_name} not found on board.")
                 return MockPin(pin_name)

            dio = digitalio.DigitalInOut(pin_obj)
            dio.direction = direction
            return dio
            
        except Exception as e:
            print(f"[HardwareManager] setup_pin {pin_name} Failed: {e}")
            return MockPin(pin_name)

    def cleanup(self):
        print("[HardwareManager] Cleaning up...")

