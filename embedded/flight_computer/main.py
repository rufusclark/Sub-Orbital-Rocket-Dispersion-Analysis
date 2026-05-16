import machine
import time
import struct
# this is not currently used by the script but has been retained for the future
from micropyGPS import MicropyGPS

# ----------------------------
# Onboard LED and battery setup
# ----------------------------
led = machine.Pin(25, machine.Pin.OUT)
vsys_adc = machine.ADC(machine.Pin(29))
charging_pin = machine.Pin(24, machine.Pin.IN)


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
        return min(100, max(0, 100 * ((voltage - self.vbat_empty) / (self.vbat_full - self.vbat_empty))))


vsys = VSYS(vsys_adc)
print_to_serial = charging_pin.value() == 1  # Only print if charging

# ----------------------------
# GPS setup
# ----------------------------
my_gps = MicropyGPS()
gps_serial = machine.UART(1, baudrate=9600, tx=4, rx=5)

# ----------------------------
# IMU (BNO055) setup
# ----------------------------
SDA_PIN = 26
SCL_PIN = 27
i2c_imu = machine.I2C(1, scl=machine.Pin(SCL_PIN),
                      sda=machine.Pin(SDA_PIN), freq=100_000)
BNO055_ADDR = 0x28


def read8_retry(reg, retries=5, delay=0.001):
    for _ in range(retries):
        try:
            return i2c_imu.readfrom_mem(BNO055_ADDR, reg, 1)[0]
        except OSError:
            time.sleep(delay)
    raise OSError(f"Failed to read reg 0x{reg:02X}")


def write8_retry(reg, value, retries=5, delay=0.001):
    for _ in range(retries):
        try:
            i2c_imu.writeto_mem(BNO055_ADDR, reg, bytes([value]))
            return
        except OSError:
            time.sleep(delay)
    raise OSError(f"Failed to write reg 0x{reg:02X}")


def read_bytes_retry(reg, length, retries=5, delay=0.001):
    for _ in range(retries):
        try:
            return i2c_imu.readfrom_mem(BNO055_ADDR, reg, length)
        except OSError:
            time.sleep(delay)
    raise OSError(f"Failed to read {length} bytes from reg 0x{reg:02X}")


BNO055_CHIP_ID = 0x00
BNO055_OPR_MODE = 0x3D
BNO055_PWR_MODE = 0x3E
BNO055_UNIT_SEL = 0x3B
BNO055_TEMP = 0x34
BNO055_EULER_H_LSB = 0x1A
BNO055_QUATERNION_W_LSB = 0x20
BNO055_LINEAR_ACCEL_X_LSB = 0x28
BNO055_GRAVITY_X_LSB = 0x2E
BNO055_ACCEL_X_LSB = 0x08
BNO055_GYRO_X_LSB = 0x14
BNO055_MAG_X_LSB = 0x0E


def bno055_init():
    chip_id = read8_retry(BNO055_CHIP_ID)
    if chip_id != 0xA0 and print_to_serial:
        print(
            "Warning: BNO055 not detected (Chip ID = 0x{:02X})".format(chip_id))
    write8_retry(BNO055_OPR_MODE, 0x00)
    time.sleep(0.025)
    write8_retry(BNO055_UNIT_SEL, 0x00)
    write8_retry(BNO055_PWR_MODE, 0x00)
    time.sleep(0.01)
    write8_retry(BNO055_OPR_MODE, 0x0C)
    time.sleep(0.02)


bno055_init()


def to_signed(val):
    if val > 32767:
        val -= 65536
    return val


def read_vector3(reg):
    data = read_bytes_retry(reg, 6)
    x = to_signed(struct.unpack('<h', data[0:2])[0])
    y = to_signed(struct.unpack('<h', data[2:4])[0])
    z = to_signed(struct.unpack('<h', data[4:6])[0])
    return x, y, z


def read_quaternion():
    data = read_bytes_retry(BNO055_QUATERNION_W_LSB, 8)
    w = to_signed(struct.unpack('<h', data[0:2])[0])
    x = to_signed(struct.unpack('<h', data[2:4])[0])
    y = to_signed(struct.unpack('<h', data[4:6])[0])
    z = to_signed(struct.unpack('<h', data[6:8])[0])
    scale = 1.0 / (1 << 14)
    return w*scale, x*scale, y*scale, z*scale


def read_euler():
    data = read_bytes_retry(BNO055_EULER_H_LSB, 6)
    h = to_signed(struct.unpack('<h', data[0:2])[0]) / 16.0
    r = to_signed(struct.unpack('<h', data[2:4])[0]) / 16.0
    p = to_signed(struct.unpack('<h', data[4:6])[0]) / 16.0
    return h, r, p


def read_temperature():
    return read8_retry(BNO055_TEMP)


def read_gyro():
    x, y, z = read_vector3(BNO055_GYRO_X_LSB)
    return x/16.0, y/16.0, z/16.0


def read_accel():
    x, y, z = read_vector3(BNO055_ACCEL_X_LSB)
    return x/100.0, y/100.0, z/100.0


def read_linear_accel():
    x, y, z = read_vector3(BNO055_LINEAR_ACCEL_X_LSB)
    return x/100.0, y/100.0, z/100.0


def read_gravity():
    x, y, z = read_vector3(BNO055_GRAVITY_X_LSB)
    return x/100.0, y/100.0, z/100.0


def read_magnetometer():
    x, y, z = read_vector3(BNO055_MAG_X_LSB)
    return x/16.0, y/16.0, z/16.0


# ----------------------------
# Barometer (BMP280) setup
# ----------------------------
i2c_baro = machine.I2C(0, scl=machine.Pin(1), sda=machine.Pin(0), freq=100_000)
BMP280_ADDR = 0x76


def bmp_read8(reg, retries=5, delay=0.001):
    for _ in range(retries):
        try:
            return i2c_baro.readfrom_mem(BMP280_ADDR, reg, 1)[0]
        except OSError:
            time.sleep(delay)
    raise OSError(f"BMP280 read8 failed {reg}")


def bmp_read16(reg, retries=5, delay=0.001):
    for _ in range(retries):
        try:
            data = i2c_baro.readfrom_mem(BMP280_ADDR, reg, 2)
            return data[1] << 8 | data[0]
        except OSError:
            time.sleep(delay)
    raise OSError(f"BMP280 read16 failed {reg}")


def bmp_read16s(reg):
    val = bmp_read16(reg)
    if val > 32767:
        val -= 65536
    return val


def bmp_write(reg, val):
    i2c_baro.writeto_mem(BMP280_ADDR, reg, bytes([val]))


# Minimal calibration
dig_T1 = bmp_read16(0x88)
dig_T2 = bmp_read16s(0x8A)
dig_T3 = bmp_read16s(0x8C)
dig_P1 = bmp_read16(0x8E)
dig_P2 = bmp_read16s(0x90)
dig_P3 = bmp_read16s(0x92)
dig_P4 = bmp_read16s(0x94)
dig_P5 = bmp_read16s(0x96)
dig_P6 = bmp_read16s(0x98)
dig_P7 = bmp_read16s(0x9A)
dig_P8 = bmp_read16s(0x9C)
dig_P9 = bmp_read16s(0x9E)


def bmp_trigger():
    bmp_write(0xF2, 0x01)
    bmp_write(0xF4, 0x25)
    while bmp_read8(0xF3) & 0x08:
        time.sleep(0.001)


def bmp_read():
    data = i2c_baro.readfrom_mem(BMP280_ADDR, 0xF7, 8)
    adc_P = (data[0] << 12) | (data[1] << 4) | (data[2] >> 4)
    adc_T = (data[3] << 12) | (data[4] << 4) | (data[5] >> 4)
    return adc_T, adc_P


def bmp_comp_T(adc_T):
    var1 = (adc_T/16384 - dig_T1/1024) * dig_T2
    var2 = ((adc_T/131072 - dig_T1/8192)**2) * dig_T3
    t_fine = var1 + var2
    T = t_fine/5120
    return T, t_fine


def bmp_comp_P(adc_P, t_fine):
    var1 = t_fine/2 - 64000
    var2 = var1*var1*dig_P6/32768
    var2 += var1*dig_P5*2
    var2 = var2/4 + dig_P4*65536
    var1 = (dig_P3*var1*var1/524288 + dig_P2*var1)/524288
    var1 = (1+var1/32768)*dig_P1
    if var1 == 0:
        return 0
    p = 1048576 - adc_P
    p = (p - var2/4096)*6250/var1
    var1 = dig_P9*p*p/2147483648
    var2 = p*dig_P8/32768
    return p + (var1+var2+dig_P7)/16


def bmp_alt(p, sea_level=101325):
    return 44330*(1 - (p/sea_level)**0.1903)

# Re-calibrate barometer if calibration is bad


retries = 5
for i in range(retries):
    try:
        # read barometer
        bmp_trigger()
        adc_T, adc_P = bmp_read()
        temp_baro, t_fine = bmp_comp_T(adc_T)

        # read imu temp
        temp_imu = read_temperature()

        if abs(temp_baro - temp_imu) < 5:
            print(
                f"Good Barometer Calibration (attempts = {i}) - {temp_baro=} {temp_imu=}")
            break
        else:
            print(
                f"Bad Barometer Calibration (attempts = {i}) - {temp_baro=} {temp_imu=}")
    except Exception as e:
        print("BMP Init Error: ", e)

    # Minimal calibration
    dig_T1 = bmp_read16(0x88)
    dig_T2 = bmp_read16s(0x8A)
    dig_T3 = bmp_read16s(0x8C)
    dig_P1 = bmp_read16(0x8E)
    dig_P2 = bmp_read16s(0x90)
    dig_P3 = bmp_read16s(0x92)
    dig_P4 = bmp_read16s(0x94)
    dig_P5 = bmp_read16s(0x96)
    dig_P6 = bmp_read16s(0x98)
    dig_P7 = bmp_read16s(0x9A)
    dig_P8 = bmp_read16s(0x9C)
    dig_P9 = bmp_read16s(0x9E)


# ----------------------------
# File setup
# ----------------------------
imu_file = "imu.csv"
baro_file = "barometer.csv"
gps_file = "gps.txt"

# Headers
with open(imu_file, "a") as f:
    f.write("===========================================\n")
    f.write("timestamp_ms,heading,roll,pitch,qw,qx,qy,qz,gx,gy,gz,ax,ay,az,lin_x,lin_y,lin_z,grav_x,grav_y,grav_z,mag_x,mag_y,mag_z,temp\n")
with open(baro_file, "a") as f:
    f.write("===========================================\n")
    f.write("timestamp_ms,temp_c,pressure_pa,alt_m\n")
with open(gps_file, "a") as f:
    f.write("===========================================\n")
    f.write("timestamp_ms,nmea_sentence\n")

# Turn LED on after initialization
led.value(1)

try:
    # ----------------------------
    # Main loop
    # ----------------------------
    imu_interval_ms = 10
    gps_interval_ms = 100
    battery_interval_ms = 100
    last_imu = time.ticks_ms()
    last_gps = time.ticks_ms()
    last_batt = time.ticks_ms()

    while True:
        now = time.ticks_ms()

        # IMU + Barometer
        if time.ticks_diff(now, last_imu) >= imu_interval_ms:
            last_imu = now
            timestamp = now
            # IMU
            try:
                heading, roll, pitch = read_euler()
                qw, qx, qy, qz = read_quaternion()
                gx, gy, gz = read_gyro()
                ax, ay, az = read_accel()
                lin_x, lin_y, lin_z = read_linear_accel()
                grav_x, grav_y, grav_z = read_gravity()
                mag_x, mag_y, mag_z = read_magnetometer()
                temp = read_temperature()
                with open(imu_file, "a") as f:
                    f.write(f"{timestamp},{heading},{roll},{pitch},{qw},{qx},{qy},{qz},{gx},{gy},{gz},{ax},{ay},{az},{lin_x},{lin_y},{lin_z},{grav_x},{grav_y},{grav_z},{mag_x},{mag_y},{mag_z},{temp}\n")
                if print_to_serial:
                    print("IMU:", timestamp, heading, roll, pitch)
            except Exception as e:
                if print_to_serial:
                    print("IMU error:", e)
                raise

            # Barometer
            try:
                bmp_trigger()
                adc_T, adc_P = bmp_read()
                temp_baro, t_fine = bmp_comp_T(adc_T)
                pressure = bmp_comp_P(adc_P, t_fine)
                alt = bmp_alt(pressure)
                with open(baro_file, "a") as f:
                    f.write(f"{timestamp},{temp_baro},{pressure},{alt}\n")
                if print_to_serial:
                    print("Baro:", timestamp, temp_baro, pressure, alt)
            except Exception as e:
                if print_to_serial:
                    print("Baro error:", e)
                raise

        # GPS
        if time.ticks_diff(now, last_gps) >= gps_interval_ms:
            last_gps = now
            timestamp = now
            while gps_serial.any():
                data = gps_serial.read()
                if data:
                    try:
                        line = data.decode("utf-8").strip()
                        with open(gps_file, "a") as f:
                            f.write(f"{timestamp},{line}\n")
                        if print_to_serial:
                            print("GPS:", timestamp, line)
                    except UnicodeError:
                        continue

        # Battery voltage print
        if time.ticks_diff(now, last_batt) >= battery_interval_ms:
            last_batt = now
            if print_to_serial:
                print(
                    f"Battery: {vsys.voltage:.2f}V, {vsys.percent_charge:.0f}%, Charging={charging_pin.value() == 1}")

except KeyboardInterrupt:
    if print_to_serial:
        print("Program stopped by user (KeyboardInterrupt).")

except Exception as e:
    if print_to_serial:
        print("Unhandled error occurred:", e)

finally:
    # Turn LED off no matter what
    led.value(0)
    if print_to_serial:
        print("LED turned off, program halted.")
