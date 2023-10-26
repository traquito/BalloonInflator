# Balloon Inflator

Tired of the manual effort of inflating pico balloons yourself?  Let a computer do it.

A combination:
- server-side python program running on raspberry pi
- front-end webpage running in your browser

This application allows you to:
- Specify lower and upper thresholds for PSI
- Automatically enable/disable an air pump to stay within those bounds
- Stop the process when a limit switch is triggered
  - This is expected to indicate the balloon is now stretched to the desired size

![Screenshot](BalloonInflator.png)


# Principle of Operation

The program uses two sensors to continuously calculate the internal pressure (PSI) exerted on the balloon.

The idea is that internal pressure on the balloon will cause the balloon to expand and ultimately stretch to a larger volume.  A final size of the balloon should be known in advance, and a limit switch used to indicate to the program that stretching is complete.

The fundamental concern of the program is to not burst the balloon by exerting too much pressure internally.  The user is able to set limits on the pressure exerted on the balloon during inflation.

To calculate the pressure exerted on the balloon the program will use two sensors, one internal to the balloon pressure, and one external.

Before the program starts, the user should click the "Snapshot Baseline" button to capture the internal and external pressure sensor value.  As the balloon is inflated, these baseline values are compared to new real-time measurements to determine the net pressure exerted on the balloon.

As the program runs, the internal pressure sensor will register an increase in pressure due to the air pump running.  The external pressure sensor will also monitor changes in the natural outside air pressure.

An increase in internal pressure alone will increase the calculated net internal pressure.  An increase of the external pressure during that time will decrease the net inernal pressure.  Other predictable variants of this scenario are accounted for.


# Hardware Requirements

Requirements:
- Raspberry Pi (any model running linux)
- Adafruit air pressure sensor module ([link](https://www.adafruit.com/product/3965)) that I found cheaper (and in stock) on amazon ([link](https://www.amazon.com/gp/product/B07JP4Y7S8/ref=ppx_yo_dt_b_asin_title_o01_s00?ie=UTF8&psc=1))
- Adafruit BME280 pressure/temp/humidity sensor ([link](https://www.adafruit.com/product/2652)) also on ebay ([link](https://www.ebay.com/sch/i.html?_from=R40&_trksid=p4432023.m570.l1313&_nkw=bme280&_sacat=0)) -- watch out for fakes
- Air pump which can be controlled via PWM
- Limit switch


# Setup
## Enable RPi I2C

> sudo raspi-config

Select Interfacing Options \
Select I2C \
Select Yes to enable I2C

Make sure your pressure sensors are plugged in and run this command. \
You should see that device 0x18 (pressure sensor) and 0x77 (BME280) responds (as shown in the table below).

Note -- the Adafruit BME280 sensor uses address 0x77, ebay or other variants may be on 0x76 or other addresses.

> sudo i2cdetect -y 1

```
     0  1  2  3  4  5  6  7  8  9  a  b  c  d  e  f
00:          -- -- -- -- -- -- -- -- -- -- -- -- --
10: -- -- -- -- -- -- -- -- 18 -- -- -- -- -- -- --
20: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
30: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
40: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
50: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
60: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
70: -- -- -- -- -- -- -- 77
```



## Software Dependency Setup

Assumes a new RPi version of Bookworm or above (2023-10-10)

> sudo rm /usr/lib/python3.11/EXTERNALLY-MANAGED

> sudo pip install aiohttp

> sudo pip install adafruit-circuitpython-mprls

> sudo pip3 install RPi.bme280

Add the following to the /etc/rc.local before the "exit 0" final line
```
/usr/bin/pigpiod
```
> sudo /etc/rc.local


## Get the Balloon Inflator software from Github

> mkdir git

> cd git

> git clone https://github.com/traquito/BalloonInflator.git

> cd BalloonInflator

> sudo ./BalloonInflator.py 24 12

### Usage

> sudo ./BalloonInflator.py

```
Usage: ./BalloonInflator.py <bcPinPwm> <bcPinLimit>
```

This is telling you that the application needs you to specify two pins:
- bcPinPwm - the pin the Pi will use to PWM the motor
- bcPinLimit - the pin the Pi will use to sense if the limit switch triggers

In both cases, the pins are the "broadcom" number, aka the "GPIOxx" number.

For example, the lower-right most pin on the RPi is GPIO21, so that would be 21 as specified to the program.

Let's see a real run:
> sudo ./BalloonInflator.py 24 12
```
======== Running on http://0.0.0.0:8080 ========
(Press CTRL+C to quit)



Application running, target browser to:
http://ballooninflator:8080/index.html
```

Here we see two GPIO pins specified for PWM and limit.

The application starts. \
Ignore the first two lines of output. \
The final line tells you the URL you can visit to run the web application.














