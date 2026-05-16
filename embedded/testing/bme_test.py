from machine import Pin, I2C
import time
import embedded.testing.bme280 as bme280  # the driver you uploaded

# Initialise I2C using GPIO 0 (SDA) and GPIO 1 (SCL)
i2c = I2C(0, scl=Pin(1), sda=Pin(0), freq=100000)

# Create the sensor object; optionally specify address
# If your module uses address 0x77, pass addr=0x77
sensor = bme280.BME280(i2c=i2c)

while True:
    # For the float driver version you can use:
    temp = sensor.temperature  # e.g. '24.53C'
    pres = sensor.pressure     # e.g. '1013.25hPa'
    try:
        hum = sensor.humidity   # e.g. '45.02%'
    except AttributeError:
        # If using BMP280 (no humidity) or driver without humidity support
        hum = None

    print("Temperature:", temp,
          "Pressure:", pres,
          "Humidity:", hum if hum is not None else "N/A")
    time.sleep(2)
