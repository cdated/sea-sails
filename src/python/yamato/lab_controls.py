#!/usr/bin/env python
from pathlib import Path
import datetime
import logging
import os
import signal
import sys
import time

from pytz import timezone
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import adafruit_dht
import board
import paho.mqtt.publish as publish
import requests
import RPi.GPIO as GPIO

pinlist = [4, 5, 6, 17, 27]
GPIO.setmode(GPIO.BCM)
GPIO.setup(pinlist, GPIO.OUT)


# Set up Logging
log = logging.getLogger("nebo")
# if 'SYSLOG_IDENTIFIER' in os.environ:
#    log.addHandler(JournaldLogHandler())
logging.basicConfig(format="%(levelname)s: %(message)s", level=logging.DEBUG)

os.chdir("/home/cdated/growlab")


sess = requests.Session()
retries = Retry(total=5, backoff_factor=0.1, status_forcelist=[500, 502, 503, 504])
sess.mount("http://", HTTPAdapter(max_retries=retries))


def get_lab_motion():
    resp = sess.get("http://shino.sealab.lan:1423/shelly/status/lab_motion")
    if resp.ok:
        if resp.text == "True":
            log.info(f"Lab motion detected -- http resp: {resp.text}")
            return True
    return False


def set_heater(state):
    publish.single(
        "sealab/gaba_lamp_break/cmnd/POWER",
        state,
        client_id="growlab",
        auth={"username": "cdated", "password": "County-Sibling-23"},
        hostname="shino.sealab.lan",
    )


def signal_handler(sig, frame):
    log.info("Cleaning up GPIO")
    GPIO.cleanup()
    sys.exit(0)


signal.signal(signal.SIGINT, signal_handler)

dhtpin = 17
HEATER_STATE = "OFF"
HEATER_TIME = None
FAN_PIN = 27
LIGHT_UNO_PIN = 5
LIGHT_DOS_PIN = 6

lon = GPIO.LOW
loff = GPIO.HIGH

# GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)

readings = []
external_reading = False
roll_temp = None
roll_humid = None

light_uno = loff
light_dos = loff
fan_pin = loff

motion_detected = False

log.info("Getting initial reading...")

ts = 0
loop_ts = 0
cnt = 0
while True:
    cnt += 1

    data_iteration = False
    if time.time() - ts > 10:
        ts = time.time()
        data_iteration = True

        # Try to grab a sensor reading.  Use the read_retry method which will retry up
        # to 15 times to get a sensor reading (waiting 2 seconds between each retry).
        try:
            dhtdev = adafruit_dht.DHT22(board.D17)
            humidity = dhtdev.humidity
            temperature = dhtdev.temperature
            external_reading = False
        except Exception:
            try:
                dhtdev = adafruit_dht.DHT22(board.D4)
                humidity = dhtdev.humidity
                temperature = dhtdev.temperature
                external_reading = True
            except Exception:
                humidity = None
                temperature = None

        # Un-comment the line below to convert the temperature to Fahrenheit.
        if humidity is not None and temperature is not None:
            temperature = temperature * 9 / 5.0 + 32
        else:
            log.warning("Failed to get reading. Try again!")

        room_temp = temperature
        if temperature is None:
            continue

        # try:
        # p = Path("data_roomlab.txt")
        # with p.open() as f:
        #    values = f.readline()
        #    room_temp, room_humidity = values.strip().split(',')
        #    room_temp = float(room_temp)
        #    room_humidity= float(room_humidity)
        #    if temperature is None:
        #        temperature = room_temp
        #
        #        humidity = room_humidity
        #        external_reading = True
        # except Exception as e:
        #    log.error(e)
        #    continue

        print(f"Temp: {temperature}   Humid: {humidity}")

        # Ignore outlier data that is 20% +/- the average
        if roll_temp and roll_humid:
            p = Path("data_growlab.txt")
            p.write_text(f"{roll_temp:0.1f},{roll_humid:0.1f}")
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

    if not room_temp:
        continue

    hotter_than_room = roll_temp > room_temp + 2
    if hotter_than_room:
        fan_pin = lon

    if roll_temp <= 68:
        fan_pin = loff

    HEATER_STATE = "OFF"
    tz = timezone("US/Eastern")
    hour = datetime.datetime.now(tz).hour
    if hour >= 9 and hour < 17:
        if roll_humid >= 48 and not hotter_than_room:
            fan_pin = loff

        if roll_humid < 45 or roll_humid > 76:
            fan_pin = lon

        light_uno = loff
        light_dos = loff

        if roll_humid >= 80 or roll_temp < 60:
            HEATER_STATE = "ON"
        else:
            HEATER_STATE = "OFF"
    else:
        if roll_temp > 80 or roll_humid < 45:
            light_uno = loff
        elif roll_temp <= 79:
            light_uno = lon

        if roll_temp > 78 or roll_humid < 48:
            light_dos = loff
        elif roll_temp <= 77:
            light_dos = lon

        # Turn on the second light on the beginning
        # of the hour in so it comes on occasionally
        time_mins = int(time.strftime("%M"))
        if time_mins <= 5:
            light_dos = lon

        # If the internal sensor is not functioning
        # keep the fan on when the light is on
        # also toggle the second light every 10 mins
        if external_reading and roll_temp >= 64:
            fan_pin = lon
            if int(time_mins / 10) % 2 != 0:
                light_dos = loff

    # try:
    #    if get_lab_motion():
    #        motion_detected = True
    #        light_uno = loff
    #        light_dos = loff
    #    else:
    #        motion_detected = False
    # except:
    #    motion_detected = False

    if cnt == 1:
        GPIO.setup(FAN_PIN, GPIO.OUT, initial=fan_pin)
        GPIO.setup(LIGHT_UNO_PIN, GPIO.OUT, initial=light_uno)
        GPIO.setup(LIGHT_DOS_PIN, GPIO.OUT, initial=light_dos)
    else:
        GPIO.output(FAN_PIN, fan_pin)
        GPIO.output(LIGHT_UNO_PIN, light_uno)
        GPIO.output(LIGHT_DOS_PIN, light_dos)

    fan = "  " if GPIO.input(FAN_PIN) is True else "++"
    heater = "  " if HEATER_STATE == "OFF" else "^^"
    light_uno_state = "  " if GPIO.input(LIGHT_UNO_PIN) is True else "L1"
    light_dos_state = "  " if GPIO.input(LIGHT_DOS_PIN) is True else "L2"

    print(
        f"Temp={temperature:0.1f}*  Humidity={humidity:0.1f}%  "
        f"Avg={roll_temp}* {roll_humid}%  | {fan} | {heater} | "
        f"{light_uno_state} | {light_dos_state}"
    )

    data_iteration = True
    time.sleep(15)
    continue

    if not data_iteration:
        continue

    prom_data = f"growlab_temp {roll_temp:0.1f}\n"
    prom_data += f"growlab_humidity {roll_humid:0.1f}\n"
    prom_data += f'growlab_heater {0 if heater=="  " else 1}\n'
    prom_data += f'growlab_fan {0 if fan=="  " else 1}\n'
    prom_data += f'growlab_light_uno {0 if light_uno_state =="  " else 1}\n'
    prom_data += f'growlab_light_dos {0 if light_dos_state =="  " else 1}\n'
    prom_data += f"growlab_external_reading {1 if external_reading else 0}\n"

    dp = Path("data_pumps.txt")
    with dp.open() as f:
        prom_data += f.readline().strip() + "\n"
        prom_data += f.readline().strip() + "\n"
        prom_data += f.readline().strip() + "\n"
        prom_data += f.readline().strip() + "\n"
        prom_data += f.readline().strip() + "\n"

    p = Path("/var/lib/node_exporter/textfile_collector/growlab.prom")
    p.write_text(prom_data)

    log.info(
        f"Temp={temperature:0.1f}*  Humidity={humidity:0.1f}%  "
        f"Avg={roll_temp}* {roll_humid}%  | {fan} | {heater} | "
        f"{light_uno_state} | {light_dos_state}"
    )

    if motion_detected:
        time.sleep(15)
    else:
        time.sleep(1)
