## Preliminary Setup

Assumes a new RPi version of Bookworm or above (2023-10-10)

> sudo rm /usr/lib/python3.11/EXTERNALLY-MANAGED
> sudo pip install aiohttp
> sudo pip install adafruit-circuitpython-mprls
> sudo pigpio
add the following to the /etc/rc.local before the "exit 0" final line
/usr/bin/pigpiod -s 1



# BalloonInflator

mkdir git
cd git
git clone https://github.com/traquito/BalloonInflator.git
cd BalloonInflator
sudo ./BalloonInflator.py 24 12




## i2c enable

> sudo raspi-config

Select 5 Interfacing Options
  Select P5 I2C
    Select Yes to enable ARM I2C

sudo i2cdetect -y 1


> sudo i2cdetect -y 1
     0  1  2  3  4  5  6  7  8  9  a  b  c  d  e  f
00:          -- -- -- -- -- -- -- -- -- -- -- -- --
10: -- -- -- -- -- -- -- -- 18 -- -- -- -- -- -- --
20: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
30: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
40: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
50: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
60: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
70: -- -- -- -- -- -- -- --

Finish installing libs
sudo pip3 install adafruit-circuitpython-mprls


run with sudo from now on


