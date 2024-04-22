# Growlab

This project uses a Raspberry Pi to control the environment of a greenhouse.

Temperature and humidity sensors are periodically read to determine if vent
fans and UV lights should be acuated. Water pumps are scheduled to run and
various other tools like a motions sensor, dehumidifier, and heater can be
used to moderate the enviroment.

# Growlab Commands

Automate lights and fans:\
`./lab_controls.py 2302 17`

Get temp/humidity outside lab:\
`./outside_sensor.py`

Automate periodic watering at daily at 6pm:\
`./water_pump.py --hour 18`

Turn off all the water pumps:\
`./water_stop.py`
