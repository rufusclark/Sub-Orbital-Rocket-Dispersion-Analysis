# For pico lipo (pimoroni)

import machine
import time

led = machine.Pin(25, machine.Pin.OUT)
vsys = machine.ADC(machine.Pin(29))        # system input voltage
# is the system connected to USB power?
charging = machine.Pin(24, machine.Pin.IN)


class VSYS:
    def __init__(self, vsys, vbat_full=4.2, vbat_empty=2.8):
        self.vsys = vsys
        self.vbat_full = vbat_full
        self.vbat_empty = vbat_empty

    @property
    def voltage(self):
        return self.vsys.read_u16() * ((3 * 3.3) / 65535)

    @property
    def percent_charge(self):
        voltage = self.voltage
        return min(100, 100 * ((voltage - self.vbat_empty) / (self.vbat_full - self.vbat_empty)))


vsys = VSYS(vsys)

while True:
    led.toggle()
    time.sleep(0.5)

    print(f"{vsys.voltage=}, {vsys.percent_charge=}, {(charging.value() == 1)=}")
