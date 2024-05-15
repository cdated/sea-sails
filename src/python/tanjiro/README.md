# Tanjiro

This project monitors 2 banks of solar batteries, a solar array, a 24v DC to 12v
DC charger, and a 12v inverter. It uses the state of each component in the
system to automatically manage all of the batteries state of charge.

The MPTT solar charger is connected to the 24v bank which is 4x larger than the
12v bank. Thus the 24v bank is the primary backup. The 12v bank is connected to
an always on inverter and handles continuous load. The 12v bank is expected to
experience a full charge cycle daily. The 12v bank is only charged during
daylight hours or when the state of charge is low. If the 24v bank will charge
the 12v bank if it has enough capacity to charge the 12v bank fully. The 24v
bank will also disable all power draw if a maintenance charge is needed, based on
the days since it last charged to 100%.

## Design Decisions

The system was originally designed to be an entirely 12v system. However, as the
solar array needed to be scaled up it became more practical to switch to a 24v
MPTT and add a 24v battery bank. Since the 12v battery and charger were already
in daily use it was fairly simple to continue using the 12v subsystem with a DC
to DC charger.

## Logging

Example logging to systemd:

```
DEBUG: +-------------------+---------------+------------------+------------+
DEBUG: |    24v  16.70%    |  12v  34.90%  |  12v load    0w  |  PV   90w  |
DEBUG: +-------------------+---------------+------------------+------------+
DEBUG: |   24v charged 0   |  charging  0  |   inverting  0   |
DEBUG: +-------------------+---------------+------------------+
DEBUG: | full 4.0 days ago |
DEBUG: +-------------------+
DEBUG: 24v is too low to run 12v 
```

