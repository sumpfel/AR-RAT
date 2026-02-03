import time
import board
import busio
import adafruit_bno055

# Initialize I2C bus
i2c = busio.I2C(board.SCL, board.SDA)

# Initialize BNO055 sensor
sensor = adafruit_bno055.BNO055_I2C(i2c)

def main():
    print("BNO055 Rotation Data (X, Y, Z)")
    print("------------------------------")
    
    while True:
        try:
            # Read Euler angles (heading, roll, pitch)
            # Note: The mapping of x, y, z depends on sensor orientation
            # Standard mapping: Heading (x), Roll (y), Pitch (z)
            euler = sensor.euler
            
            if euler:
                # Format to 2 decimal places
                print("X: {:<10.2f} Y: {:<10.2f} Z: {:<10.2f}".format(
                    euler[0] if euler[0] is not None else 0,
                    euler[1] if euler[1] is not None else 0,
                    euler[2] if euler[2] is not None else 0
                ))
            else:
                print("Waiting for data...")
                
        except RuntimeError as e:
            # I2C can sometimes time out or have errors
            print(f"Sensor error: {e}")
        except KeyboardInterrupt:
            print("\nExiting...")
            break
            
        time.sleep(0.1)

if __name__ == "__main__":
    main()
