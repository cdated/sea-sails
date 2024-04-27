#!/usr/bin/python

from pathlib import Path
import datetime
import logging
import os
import signal
import sys
import time

from pytz import timezone
import click
import RPi.GPIO as GPIO

# from systemd.journal import JournaldLogHandler

# Set up Logging
log = logging.getLogger("nebo")
# if 'SYSLOG_IDENTIFIER' in os.environ:
#    log.addHandler(JournaldLogHandler())
logging.basicConfig(format="%(levelname)s: %(message)s", level=logging.DEBUG)


os.chdir("/home/cdated/growlab")


HEATER_PIN = 18
LIGHT_UNO_PIN = 5
LIGHT_DOS_PIN = 6

A = 13  # purple
B = 19  # yellow
C = 26  # blue
D = 16  # red

A_TIME = 540  # 9.0min
B_TIME = 390  # 6.5min
C_TIME = 450  # 7.5min
D_TIME = 270  # 4.5min


def gpio_setup():
    # GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(A, GPIO.OUT, initial=GPIO.HIGH)
    GPIO.setup(B, GPIO.OUT, initial=GPIO.HIGH)
    GPIO.setup(C, GPIO.OUT, initial=GPIO.HIGH)
    GPIO.setup(D, GPIO.OUT, initial=GPIO.HIGH)


def run_pumps():
    # run_pump("purple", A_TIME, A)
    # time.sleep(300)
    run_pump("blue", C_TIME, C)
    time.sleep(300)
    run_pump("yellow", B_TIME, B)
    time.sleep(300)
    run_pump("red", D_TIME, D)


def run_pump(name, duration, gpio):
    write_pump_state(name)
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(gpio, GPIO.OUT, initial=GPIO.LOW)
    while duration > 0:
        log.info(f"{name}: {duration}s")
        duration -= 1
        time.sleep(1)
    GPIO.output(gpio, GPIO.HIGH)
    write_pump_state(None)


def write_pump_state(name):
    p = Path("data_pumps.txt")
    pump_data = ""
    for pump in ["purple", "blue", "yellow", "red"]:
        if pump == name:
            pump_data += f"pump_{pump}_on 1\n"
        else:
            pump_data += f"pump_{pump}_on 0\n"
        p.write_text(pump_data)


def all_stop():
    GPIO.output(A, GPIO.HIGH)
    GPIO.output(B, GPIO.HIGH)
    GPIO.output(C, GPIO.HIGH)
    GPIO.output(D, GPIO.HIGH)
    GPIO.cleanup()


def signal_handler(sig, frame):
    log.info("Stopping all pumps")
    all_stop()
    sys.exit(0)


@click.command()
@click.option("--hour", default=-1, help="Hour of the day to run pumps")
@click.option("--stop", is_flag=True, help="Stop water pumps")
def main(hour, stop):
    signal.signal(signal.SIGINT, signal_handler)
    tz = timezone("US/Eastern")

    write_pump_state("none")

    if stop:
        all_stop()
        sys.exit(0)

    if hour == -1:
        run_pumps()
        all_stop()
        sys.exit(0)

    while True:
        curr_time = datetime.datetime.now(tz)
        cur_hour = curr_time.hour
        cur_mins = curr_time.minute
        dow = time.strftime("%a")
        p = Path("data_growlab.txt")
        try:
            with p.open() as f:
                values = f.readline()
                temperature, humidity = values.strip().split(",")
        except IOError:
            log.error(f"Error: Incorrect growlab data -- {values}")
        log.info(f"{dow} - {cur_hour:02}:{cur_mins:02}  {temperature}* {humidity}%")

        if hour == int(cur_hour) and 54 == int(cur_mins):
            run_pumps()
            all_stop()
        time.sleep(60)


if __name__ == "__main__":
    gpio_setup()
    main()
