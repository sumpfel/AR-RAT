
import board
import microcontroller

print("Board pins:", dir(board))
print("Microcontroller pins:", dir(microcontroller.pin))

# Try to identify C8/C9 in microcontroller.pin if they exist
# On FT232H, valid pins are often D0-D7 and C0-C9 (ACBUS)
# Let's inspect what's available.
