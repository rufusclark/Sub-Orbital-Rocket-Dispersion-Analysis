from machine import Pin, I2C
import time
import math

# ----------------------------
# I2C setup
# ----------------------------
i2c = I2C(0, scl=Pin(1), sda=Pin(0), freq=100_000)
time.sleep(1)  # allow sensor to boot

BMP280_ADDR = 0x76  # BME280 default address

# ----------------------------
# I2C read functions with retry
# ----------------------------


def read8_retry(reg, retries=5, delay=0.01):
    for _ in range(retries):
        try:
            return i2c.readfrom_mem(BMP280_ADDR, reg, 1)[0]
        except OSError:
            time.sleep(delay)
    raise OSError(f"Failed to read reg 0x{reg:02X}")


def read16_retry(reg, retries=5, delay=0.01):
    for _ in range(retries):
        try:
            data = i2c.readfrom_mem(BMP280_ADDR, reg, 2)
            return data[1] << 8 | data[0]
        except OSError:
            time.sleep(delay)
    raise OSError(f"Failed to read reg 0x{reg:02X}")


def read16s_retry(reg, retries=5, delay=0.01):
    val = read16_retry(reg, retries, delay)
    if val > 32767:
        val -= 65536
    return val


def write_reg(reg, value):
    i2c.writeto_mem(BMP280_ADDR, reg, bytes([value]))


# ----------------------------
# Calibration read with retries
# ----------------------------
max_calibration_attempts = 3
for attempt in range(max_calibration_attempts):
    try:
        # Temperature calibration
        dig_T1 = read16_retry(0x88)
        dig_T2 = read16s_retry(0x8A)
        dig_T3 = read16s_retry(0x8C)

        # Pressure calibration
        dig_P1 = read16_retry(0x8E)
        dig_P2 = read16s_retry(0x90)
        dig_P3 = read16s_retry(0x92)
        dig_P4 = read16s_retry(0x94)
        dig_P5 = read16s_retry(0x96)
        dig_P6 = read16s_retry(0x98)
        dig_P7 = read16s_retry(0x9A)
        dig_P8 = read16s_retry(0x9C)
        dig_P9 = read16s_retry(0x9E)

        # Humidity calibration
        dig_H1 = read8_retry(0xA1)
        dig_H2 = read16s_retry(0xE1)
        dig_H3 = read8_retry(0xE3)
        e4 = read8_retry(0xE4)
        e5 = read8_retry(0xE5)
        e6 = read8_retry(0xE6)
        dig_H4 = (e4 << 4) | (e5 & 0x0F)
        dig_H5 = (e6 << 4) | (e5 >> 4)
        dig_H6 = read8_retry(0xE7)
        if dig_H6 > 127:
            dig_H6 -= 256

        break  # success
    except OSError as e:
        print(
            f"Calibration read failed, attempt {attempt+1}/{max_calibration_attempts}: {e}")
        time.sleep(0.05)
else:
    raise RuntimeError("Failed to read BME280 calibration data after retries")

# ----------------------------
# Compensation functions
# ----------------------------


def read_raw_data():
    data = i2c.readfrom_mem(BMP280_ADDR, 0xF7, 8)
    adc_p = (data[0] << 12) | (data[1] << 4) | (data[2] >> 4)
    adc_t = (data[3] << 12) | (data[4] << 4) | (data[5] >> 4)
    adc_h = (data[6] << 8) | data[7]
    return adc_t, adc_p, adc_h


def compensate_T(adc_T):
    var1 = (adc_T / 16384.0 - dig_T1 / 1024.0) * dig_T2
    var2 = ((adc_T / 131072.0 - dig_T1 / 8192.0) ** 2) * dig_T3
    t_fine = var1 + var2
    T = t_fine / 5120.0
    return T, t_fine


def compensate_P(adc_P, t_fine):
    var1 = t_fine / 2.0 - 64000.0
    var2 = var1 * var1 * dig_P6 / 32768.0
    var2 = var2 + var1 * dig_P5 * 2.0
    var2 = var2 / 4.0 + dig_P4 * 65536.0
    var1 = (dig_P3 * var1 * var1 / 524288.0 + dig_P2 * var1) / 524288.0
    var1 = (1.0 + var1 / 32768.0) * dig_P1
    if var1 == 0:
        return 0
    p = 1048576.0 - adc_P
    p = (p - var2 / 4096.0) * 6250.0 / var1
    var1 = dig_P9 * p * p / 2147483648.0
    var2 = p * dig_P8 / 32768.0
    p = p + (var1 + var2 + dig_P7) / 16.0
    return p


def compensate_H(adc_H, t_fine):
    v_x1 = t_fine - 76800.0
    v_x1 = (adc_H - (dig_H4 * 64.0 + dig_H5 / 16384.0 * v_x1)) * \
           (dig_H2 / 65536.0 * (1.0 + dig_H6 / 67108864.0 *
            v_x1 * (1.0 + dig_H3 / 67108864.0 * v_x1)))
    v_x1 = max(0, min(v_x1, 100))
    return v_x1


def altitude(pressure, sea_level_pa=101325.0):
    return 44330.0 * (1.0 - (pressure / sea_level_pa) ** 0.1903)

# ----------------------------
# Trigger measurement with polling
# ----------------------------


def trigger_measurement():
    write_reg(0xF2, 0x01)  # humidity x1
    write_reg(0xF4, 0x25)  # forced mode, temp+press x1
    # poll status register until measuring bit is cleared
    while read8_retry(0xF3) & 0x08:
        time.sleep(0.005)


# ----------------------------
# Main loop
# ----------------------------
while True:
    try:
        trigger_measurement()
        adc_T, adc_P, adc_H = read_raw_data()
        temp, t_fine = compensate_T(adc_T)
        pressure = compensate_P(adc_P, t_fine)
        humidity = compensate_H(adc_H, t_fine)
        alt = altitude(pressure)
        print("Temp: {:.2f} °C, Pressure: {:.2f} hPa, Humidity: {:.2f} %, Altitude: {:.2f} m".format(
            temp, pressure/100, humidity, alt))
        time.sleep(0.01)
    except OSError as e:
        print("I2C read error:", e)
        time.sleep(0.05)  # short delay before retry
