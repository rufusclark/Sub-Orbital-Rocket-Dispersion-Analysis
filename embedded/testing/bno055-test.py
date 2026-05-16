from machine import Pin, I2C
from time import sleep
from embedded.testing.bno055 import BNO055

# Initialize I2C (change pins if needed)
i2c = I2C(1, scl=Pin(27), sda=Pin(26))

# Scan for device
print("I2C devices found:", i2c.scan())

# Initialize sensor
bno = BNO055(i2c)

# Read orientation
while True:
    heading, roll, pitch = bno.read_euler()
    print("Heading: %.2f Roll: %.2f Pitch: %.2f" % (heading, roll, pitch))
    sleep(0.5)
