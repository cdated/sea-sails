#!/usr/bin/python

import datetime
import json
import os
import signal
import time

import requests
import sdnotify

n = sdnotify.SystemdNotifier()
n.notify("READY=1")

import logging

import paho.mqtt.publish as publish
import paho.mqtt.subscribe as subscribe
from pytz import timezone
from systemd.journal import JournaldLogHandler

# Set up Logging
log = logging.getLogger("nebo")
if "SYSLOG_IDENTIFIER" in os.environ:
    log.addHandler(JournaldLogHandler())
logging.basicConfig(format="%(levelname)s: %(message)s", level=logging.DEBUG)


SOC12V = "N/b827eb62c15b/battery/291/Soc"
SOC24V = "N/b827eb62c15b/battery/288/Soc"
PV_POWER = "N/b827eb62c15b/solarcharger/289/Yield/Power"
SOC24_SEC_SINCE_FULL = "N/b827eb62c15b/battery/288/History/TimeSinceLastFullCharge"
INVERTER_LOAD = "N/b827eb62c15b/battery/291/Dc/0/Power"

HOMEASSISTANT = os.environ["HOMEASSISTANT"]
HA_AUTH = os.environ["HA_AUTH"]

mqtt_user = os.environ["MQTT_USER"]
mqtt_pass = os.environ["MQTT_PASS"]
MQTT_AUTH = {"username": mqtt_user, "password": mqtt_pass}

# The Vicron Venus raspberry pi
TANJIRO = os.environ["TANJIRO"]


class MqttException(Exception):
    pass


class timeout:
    def __init__(self, seconds=1, error_message="Timeout"):
        self.seconds = seconds
        self.error_message = error_message

    def handle_timeout(self, signum, frame):
        raise TimeoutError(self.error_message)

    def __enter__(self):
        signal.signal(signal.SIGALRM, self.handle_timeout)
        signal.alarm(self.seconds)

    def __exit__(self, type, value, traceback):
        signal.alarm(0)


def main():
    # Start with the 12v charger disabled
    # log.debug("-- Turning off charger --")
    # control_12v_charger(state_on=False)
    charging = state_12v_charger()
    log.debug(f"-- Charging State: {charging} --")

    ran_once = False
    soc24charged = True

    while True:
        n.notify("STATUS=Running")
        n.notify("WATCHDOG=1")
        if ran_once:
            time.sleep(10)
        else:
            ran_once = True

        log.debug("VictronPi KeepAlive sending")
        # Should be 'tanjiro.sealab.lan'
        publish.single("R/b827eb62c15b/keepalive", hostname=TANJIRO, auth=MQTT_AUTH)  # send 'keepalive' message
        log.debug("VictronPi KeepAlive sent")

        try:
            log.debug("Getting 24v SOC from MQTT")
            soc24 = get_state_of_charge(SOC24V)

            log.debug("Getting 24v days since full from MQTT")
            days_since_soc24_full = get_days_since_soc24_full()

            log.debug("Getting PV Power")
            pv_power = get_pv_power()

            log.debug("Getting 12v SOC from MQTT")
            soc12 = get_state_of_charge(SOC12V)
            if soc12 <= 15:
                log.debug("12v SOC below 15%, enabling charger")
                x = control_12v_charger(state_on=True)
                charging = True

            if is_inverting():
                log.debug("Getting inverter load")
                power_12v = get_inverter_load()
                if soc12 <= 15:
                    log.debug("Disabling Inverter")
                    toggle_inverter()
            else:
                power_12v = 0
        except MqttException:
            time.sleep(1)
            continue

        log.debug("+--------------+---------------+-------------------+----------+")
        log.debug(f"| 24v {soc24:6.2f}%  |  12v {soc12:6.2f}%  |  12v Power {power_12v:4.0f}w  | PV {pv_power:4.0f}w |")
        log.debug("+--------------+---------------+-------------------+----------+")

        # Everything is pretty much dead just loop until things get better
        if soc12 > 15 and soc24 <= 15:
            log.debug("24v is low and 12v is charged enough")
            x = control_12v_charger(state_on=False)
            charging = False
            continue

        tz = timezone("US/Eastern")
        log.debug(datetime.datetime.now(tz))
        hour = datetime.datetime.now(tz).hour
        daytime = hour >= 9 and hour < 19
        if charging and (not daytime) and soc12 >= 80:
            log.debug("-- Turning off charger --")
            control_12v_charger(state_on=False)
            charging = False

        inverting = is_inverting()

        if days_since_soc24_full >= 60 and soc12 >= 90:
            log.debug("SOC24 needs a balance change")
            log.debug("Disabling inverter and 12v charger")
            if inverting:
                log.debug("Disabling Inverter")
                toggle_inverter()
            if charging:
                log.debug("-- Turning off charger --")
                charging = control_12v_charger(state_on=False)
                log.debug(f"-- Charging State: {charging} --")
            continue

        if soc24 >= 35 and soc12 >= 80 and not inverting:
            log.debug("Enabling Inverter")
            toggle_inverter()

        charging = state_12v_charger()
        log.debug(f"-- Charging State: {charging} --")

        # Don't charge 12v if the 24v is too low
        if soc24 <= 10:
            soc24charged = False
            if charging:
                log.debug("-- Turning off charger --")
                x = control_12v_charger(state_on=False)
                print(x)
                charging = False
            continue
        elif soc24 >= 30:
            soc24charged = True

        log.debug(f"Is daytime: {daytime}")
        log.debug(f"Is soc24charged: {soc24charged}")
        log.debug(f"Is inverting: {inverting}")
        log.debug(f"Is charging: {charging}")

        # If 24v is nearly full run the 12v charger before peak sun
        # but only if the inverter conditions are true
        if daytime and soc24charged and not charging:
            log.debug("-- Turning on charger for daylight--")
            x = control_12v_charger(state_on=True)
            print(x)
            charging = True
            continue

        # Charge the 12v if the SOC have reached 10%
        # or if the 24v is low only discharge to 20% since further charging is less likely
        if soc24charged and not charging:
            if (soc24 <= 35 and soc12 <= 20) or soc12 <= 10:
                log.debug("-- Turning on charger --")
                x = control_12v_charger(state_on=True)
                print(x)
                charging = True
                continue


def toggle_inverter():
    log.debug("-- Toggling Inverter --")
    url = f"{HOMEASSISTANT}/api/services/automation/trigger"
    data = {"entity_id": "automation.inverter_momentary_switch"}
    headers = {
        "Authorization": HA_AUTH,
        "Content-Type": "application/json",
    }
    x = requests.post(url, json=data, headers=headers)
    log.debug(f"-- Inverter Response: {x} --")
    log.debug("Sleeping 5 min")
    time.sleep(300)


def control_12v_charger(state_on):
    if state_on:
        action = "turn_on"
    else:
        action = "turn_off"

    log.debug(f"-- Setting 12v action {action} --")
    url = f"{HOMEASSISTANT}/api/services/switch/{action}"
    data = {"entity_id": "switch.12v_charger_remote"}
    headers = {
        "Authorization": HA_AUTH,
        "Content-Type": "application/json",
    }
    x = requests.post(url, json=data, headers=headers)
    log.debug(f"-- 12v Charger Response: {x} --")
    return x


def state_12v_charger():
    try:
        with timeout(seconds=5):
            log.debug("-- Getting 12v charger state --")
            url = f"{HOMEASSISTANT}/api/states/switch.12v_charger_remote"
            headers = {
                "Authorization": HA_AUTH,
                "Content-Type": "application/json",
            }
            x = requests.get(url, headers=headers)
            log.debug(f"-- 12v Charger Response: {x} --")
            x = json.loads(x.text)
            return x.get("state") == "on"

    except:
        log.info("Failed to get 12v charger state")
        return False


def is_inverting():
    log.debug("-- Getting Inverter Meter State --")
    url = f"{HOMEASSISTANT}/api/states/sensor.inverter_meter_voltage"
    headers = {
        "Authorization": HA_AUTH,
        "Content-Type": "application/json",
    }
    x = requests.get(url, headers=headers)
    x = json.loads(x.text)
    log.debug(f"-- Inverter Meter Response: {x.get('state')} --")
    if x.get("state") is None:
        return False

    return x.get("state") != "unavailable"


def get_days_since_soc24_full():
    try:
        with timeout(seconds=1):
            msg = subscribe.simple(SOC24_SEC_SINCE_FULL, hostname=TANJIRO, auth=MQTT_AUTH)
    except:
        log.info("Failed to connect to venus MQTT")
        raise MqttException

    ssf = msg.payload.decode("utf-8")
    ssf = json.loads(ssf)
    log.debug(f"Got SOC24 sec since full {ssf}")
    ssf = float("{:.2f}".format(ssf["value"]))
    mins = ssf / 60
    hours = mins / 60
    days = hours / 24
    days = float("{:.2f}".format(days))
    log.debug(f"Got SOC24 days since full {days}")
    return days


def get_state_of_charge(battery):
    try:
        with timeout(seconds=1):
            msg = subscribe.simple(battery, hostname=TANJIRO, auth=MQTT_AUTH)
    except:
        log.info("Failed to connect to venus MQTT")
        raise MqttException

    soc = msg.payload.decode("utf-8")
    soc = json.loads(soc)
    log.debug(f"Got SOC paload {soc}")
    charge = float("{:.2f}".format(soc["value"]))
    return charge


def get_inverter_load():
    try:
        with timeout(seconds=1):
            msg = subscribe.simple(INVERTER_LOAD, hostname=TANJIRO, auth=MQTT_AUTH)
    except:
        log.info("Failed to connect to venus MQTT")
        return 0
        raise MqttException

    resp = msg.payload.decode("utf-8")
    power = json.loads(resp)
    log.debug(f"Resp inverter load {power}")
    load = float("{:.2f}".format(power["value"]))
    return load


def get_pv_power():
    try:
        with timeout(seconds=1):
            msg = subscribe.simple(PV_POWER, hostname=TANJIRO, auth=MQTT_AUTH)
    except:
        log.info("Failed to connect to venus MQTT")
        raise MqttException

    resp = msg.payload.decode("utf-8")
    power = json.loads(resp)
    log.debug(f"Resp PV power {power}")
    load = float("{:.2f}".format(power["value"]))
    return load


if __name__ == "__main__":
    main()
