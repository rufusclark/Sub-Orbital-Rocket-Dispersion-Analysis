# This requires the micropyGPS.py module (copy and paste is recommended as this does not ship with MicroPython)

import machine  # type: ignore
from time import sleep
from micropyGPS import MicropyGPS

print("Starting GPS Test")

# init micropyGPS object
my_gps = MicropyGPS()

# Define the UART pins and create the UART object
gps_serial = machine.UART(1, baudrate=9600, tx=8, rx=9)

# Decoded messages
while True:
    try:
        while gps_serial.any():
            data = gps_serial.read()
            for byte in data:
                stat = my_gps.update(chr(byte))
                if stat is not None:
                    # Print parsed GPS data
                    print('UTC Timestamp:', my_gps.timestamp)
                    print('Date:', my_gps.date_string('long'))
                    print('Latitude:', my_gps.latitude_string())
                    print('Longitude:', my_gps.longitude_string())
                    print('Altitude:', my_gps.altitude)
                    print('Satellites in use:', my_gps.satellites_in_use)
                    print('Horizontal Dilution of Precision:', my_gps.hdop)
                    print()

    except Exception as e:
        print(f"An error occurred: {e}")

# Check and print all outputs
while True:
    if gps_serial.any():
        line = gps_serial.readline()
        if line:
            try:
                line = line.decode('utf-8').strip()
                print(line)
                for x in line:
                    my_gps.update(x)
            except UnicodeError:
                continue  # ignore bad characters
    sleep(1)
