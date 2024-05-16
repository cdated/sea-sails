#!/usr/bin/env python

from pathlib import Path
import logging
import time

import RPi.GPIO as GPIO

# from systemd.journal import JournaldLogHandler

# Set up Logging
log = logging.getLogger("nebo")
# if 'SYSLOG_IDENTIFIER' in os.environ:
#    log.addHandler(JournaldLogHandler())
logging.basicConfig(format="%(levelname)s: %(message)s", level=logging.DEBUG)


GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)

heater = ""
readings = []

roll_temp = None
roll_humid = None

while True:
    # Try to grab a sensor reading.  Use the read_retry method which will retry up
    # to 15 times to get a sensor reading (waiting 2 seconds between each retry).

    # TODO: add GPIO temp/humidity sensor readings
    humidity, temperature = (None, None)

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

        temp = temperature
        humid = humidity
        log.info(
            f"Temp={temp:0.1f}*  Humidity={humid:0.1f}%  Avg={roll_temp}* {roll_humid}%  | {heater}"
        )
    else:
        log.warning("Failed to get reading. Try again!")

    time.sleep(10)
