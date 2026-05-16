import machine
import utime
import os

os.chdir("/")

with open("/data.txt", "w") as f:
    f.write("Hello World")

print(os.listdir())
