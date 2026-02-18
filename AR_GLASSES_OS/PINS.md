# AR OS Pinout & Controls

This document details the wiring for the AR Glasses OS control buttons and the keyboard shortcuts available in "Software Mode".

## Hardware Buttons

The system supports both **FT232H USB GPIO** and **Raspberry Pi Native GPIO**. The hardware is auto-detected.

| Function | FT232H Pin | Raspberry Pi (BCM) | Keyboard |
|:---:|:---:|:---:|:---:|
| **UP** | D4 | GPIO 24 | Arrow Up |
| **DOWN** | C3 | GPIO 23 | Arrow Down |
| **LEFT** | C4 | GPIO 5 | Arrow Left |
| **RIGHT** | C6 | GPIO 6 | Arrow Right |
| **SELECT** | C1 | GPIO 27 | Enter |
| **BACK** | C0 | GPIO 17 | Esc |
| **MENU** | C2 | GPIO 22 | Tab / M |
| **LAUNCHER** | N/A | N/A | L |

> **Note:** Pin mappings can be customized in `config.py`.

## Wiring

Connect buttons between the specified **Pin** and **GND**. The internal pull-up/pull-down configuration is handled by the software (Check `HardwareManager` for specific logic, usually expects Active High or Low depending on implementation. *Current implementation assumes Active High based on `if val:` check, so buttons should connect VCC to Pin with Pull-down, OR logic should be inverted if using internal Pull-ups.*)

**Correction**: Looking at `core/input_manager.py`:
```python
val = btn.value 
is_pressed = val 
```
This implies **Active High**.
- Connect Button specific Pin to **3.3V**.
- Ensure Pulldown resistors are used (if not internal). 
*Note: `HardwareManager` does not explicitly set Pull direction in `setup_pin`, so external pulldowns are recommended.*

## Running in Software Mode

If no supported hardware is detected, the system will automatically fall back to **MOCK** mode. 
You can use the **Keyboard** shortcuts listed above to navigate the UI.
