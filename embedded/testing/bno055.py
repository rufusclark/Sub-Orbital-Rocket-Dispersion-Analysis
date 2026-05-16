import time
from machine import I2C

BNO055_ADDRESS_A = 0x28
BNO055_ID = 0xA0

# Register addresses
BNO055_CHIP_ID_ADDR = 0x00
BNO055_OPR_MODE_ADDR = 0x3D
BNO055_PWR_MODE_ADDR = 0x3E
BNO055_SYS_TRIGGER_ADDR = 0x3F
BNO055_UNIT_SEL_ADDR = 0x3B
BNO055_AXIS_MAP_CONFIG_ADDR = 0x41
BNO055_AXIS_MAP_SIGN_ADDR = 0x42
BNO055_CALIB_STAT_ADDR = 0x35
BNO055_EULER_H_LSB_ADDR = 0x1A

# Operation modes
OPERATION_MODE_CONFIG = 0x00
OPERATION_MODE_NDOF = 0x0C


class BNO055:
    def __init__(self, i2c, address=BNO055_ADDRESS_A):
        self.i2c = i2c
        self.address = address
        self._init_sensor()

    def _write(self, reg, value):
        self.i2c.writeto_mem(self.address, reg, bytes([value]))

    def _read(self, reg, length=1):
        return self.i2c.readfrom_mem(self.address, reg, length)

    def _init_sensor(self):
        chip_id = self._read(BNO055_CHIP_ID_ADDR)[0]
        if chip_id != BNO055_ID:
            raise Exception("BNO055 not found")
        self._write(BNO055_OPR_MODE_ADDR, OPERATION_MODE_CONFIG)
        time.sleep(0.025)
        self._write(BNO055_SYS_TRIGGER_ADDR, 0x00)
        self._write(BNO055_PWR_MODE_ADDR, 0x00)
        time.sleep(0.01)
        self._write(BNO055_OPR_MODE_ADDR, OPERATION_MODE_NDOF)
        time.sleep(0.02)

    def read_euler(self):
        data = self._read(BNO055_EULER_H_LSB_ADDR, 6)
        heading = (data[1] << 8) | data[0]
        roll = (data[3] << 8) | data[2]
        pitch = (data[5] << 8) | data[4]
        return (heading / 16.0, roll / 16.0, pitch / 16.0)
