#!/usr/bin/env python
# Copyright (c) 2014 Adafruit Industries
# Author: Tony DiCola

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.

import logging

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
import sys
import time
from pathlib import Path

import RPi.GPIO as GPIO

# from systemd.journal import JournaldLogHandler

# Set up Logging
log = logging.getLogger("nebo")
# if 'SYSLOG_IDENTIFIER' in os.environ:
#    log.addHandler(JournaldLogHandler())
logging.basicConfig(format="%(levelname)s: %(message)s", level=logging.DEBUG)


# Parse command line parameters.
sensor_args = {
    "11": Adafruit_DHT.DHT11,
    "22": Adafruit_DHT.DHT22,
    "2302": Adafruit_DHT.AM2302,
}
if len(sys.argv) == 3 and sys.argv[1] in sensor_args:
    sensor = sensor_args[sys.argv[1]]
    pin = sys.argv[2]

elif len(sys.argv) == 1:
    sensor = Adafruit_DHT.AM2302
    pin = "4"
else:
    print("Usage: sudo ./Adafruit_DHT.py [11|22|2302] <GPIO pin number>")
    print(
        "Example: sudo ./Adafruit_DHT.py 2302 4 - Read from an AM2302 connected to GPIO pin #4"
    )
    sys.exit(1)


GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)

heater = ""
readings = []

roll_temp = None
roll_humid = None

while True:
    # Try to grab a sensor reading.  Use the read_retry method which will retry up
    # to 15 times to get a sensor reading (waiting 2 seconds between each retry).
    humidity, temperature = Adafruit_DHT.read_retry(sensor, pin)

    # Un-comment the line below to convert the temperature to Fahrenheit.
    if humidity is not None and temperature is not None:
        temperature = temperature * 9 / 5.0 + 32

        # Ignore outlier data that is 20% +/- the average
        if roll_temp and roll_humid:
            if temperature < roll_temp * 0.8 or temperature > roll_temp * 1.2:
                continue
            if humidity < roll_humid * 0.8 or humidity > roll_humid * 1.2:
                continue

        readings.append((temperature, humidity))
        if len(readings) == 13:
            readings.pop(0)

        temp_readings = [reading[0] for reading in readings]
        humid_readings = [reading[1] for reading in readings]
        roll_temp = round(sum(temp_readings) / len(temp_readings), 1)
        roll_humid = round(sum(humid_readings) / len(humid_readings), 1)

        p = Path("/var/lib/node_exporter/textfile_collector/roomlab.prom")
        prom_data = f"roomlab_temp {roll_temp:0.1f}\n"
        prom_data += f"roomlab_humidity {roll_humid:0.1f}\n"
        p.write_text(prom_data)

        p = Path("data_roomlab.txt")
        prom_data = f"{roll_temp:0.1f},{roll_humid:0.1f}"
        p.write_text(prom_data)

        log.info(
            f"Temp={temperature:0.1f}*  Humidity={humidity:0.1f}%  Avg={roll_temp}* {roll_humid}%  | {heater}"
        )
    else:
        log.warning("Failed to get reading. Try again!")

    time.sleep(10)
