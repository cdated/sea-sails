#!/usr/bin/env python

import signal
import sys
import time
from pathlib import Path

import click
import RPi.GPIO as GPIO

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
    #    run_pump("purple", A_TIME, A)
    #    run_pump("blue", C_TIME, C)
    run_pump("yellow", B_TIME, B)
    run_pump("red", D_TIME, D)


def run_pump(name, duration, gpio):
    write_pump_state(name)
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(gpio, GPIO.OUT, initial=GPIO.LOW)
    while duration > 0:
        print(f"{name}: {duration}s")
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
    print("Stopping all pumps")
    all_stop()
    sys.exit(0)


temperature = 0


@click.command()
def main():
    signal.signal(signal.SIGINT, signal_handler)

    cur_hour = int(time.strftime("%H"))
    cur_mins = int(time.strftime("%M"))
    dow = time.strftime("%a")
    p = Path("data_growlab.txt")
    try:
        with p.open() as f:
            values = f.readline()
            temperature, humidity = values.strip().split(",")
    except:
        print(f"Error: Incorrect growlab data -- {values}")
    else:
        print(f"{dow} - {cur_hour:02}:{cur_mins:02}  {temperature}* {humidity}%")

    run_pumps()
    all_stop()


if __name__ == "__main__":
    gpio_setup()
    main()
