import serial
import time
import binascii

# BNO055 Constants
BNO055_ID_ADDR = 0x00
BNO055_PAGE_ID_ADDR = 0x07

def send_read_request(ser, reg_addr):
    # Command: 0xAA (Start), 0x01 (Read), RegAddr, length (1)
    # The BNO055 UART protocol
    cmd = bytearray([0xAA, 0x01, reg_addr, 0x01])
    ser.write(cmd)
    
def main():
    print("Opening Serial Port /dev/serial0 at 115200 baud...")
    try:
        ser = serial.Serial('/dev/serial0', 115200, timeout=1.0)
    except Exception as e:
        print(f"Error opening serial port: {e}")
        return

    print("Port open. Flushing buffers...")
    ser.reset_input_buffer()
    ser.reset_output_buffer()
    time.sleep(0.5)

    print("Sending 'Read Chip ID' command (Reg 0x00)...")
    send_read_request(ser, BNO055_ID_ADDR)
    
    time.sleep(0.1)
    
    if ser.in_waiting > 0:
        print(f"Received {ser.in_waiting} bytes:")
        response = ser.read(ser.in_waiting)
        print(f"Hex: {binascii.hexlify(response).decode('utf-8')}")
        
        if len(response) >= 2 and response[0] == 0xBB:
            print("Success! Response Header 0xBB found.")
        else:
            print("Response does not look like BNO055 response (Head 0xBB).")
    else:
        print("No response received.")
        print("\nTroubleshooting Tips:")
        print("1. WIRING: Is TX connected to RX and RX to TX?")
        print("   - Sensor TX -> Pi RX (GPIO 15, pin 10)")
        print("   - Sensor RX -> Pi TX (GPIO 14, pin 8)")
        print("2. MODE: Are PS0 and PS1 set for UART?")
        print("   - PS1 -> VIN (High)")
        print("   - PS0 -> GND (Low)")
        print("   (If PS1 is Low, it thinks it's I2C)")

    ser.close()

if __name__ == "__main__":
    main()
