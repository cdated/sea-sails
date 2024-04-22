#!/usr/bin/python
import sys
import time

from pathlib import Path
import RPi.GPIO as GPIO
import Adafruit_DHT


HEATER_PIN=18
LIGHT_UNO_PIN=5
LIGHT_DOS_PIN=6

A=13 # purple
B=19 # yellow
C=26 # blue
D=16 # red

GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)
GPIO.setup(A, GPIO.OUT, initial=GPIO.HIGH)
GPIO.setup(B, GPIO.OUT, initial=GPIO.HIGH)
GPIO.setup(C, GPIO.OUT, initial=GPIO.HIGH)
GPIO.setup(D, GPIO.OUT, initial=GPIO.HIGH)
