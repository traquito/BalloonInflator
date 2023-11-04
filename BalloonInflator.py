#!/usr/bin/env -S python3 -u

import os
import re
import random
import sys
import time
import asyncio
import socket
import bme280
import smbus2


try:
    import pigpio
except:
    print("")
    print("You don't have pigpio installed, you need that")
    print("Install instructions here:")
    print("https://abyz.me.uk/rpi/pigpio/download.html")
    print("")
    os._exit(-1)

try:
    from aiohttp import web
except:
    print("")
    print("You don't have aiohttp installed, you need that")
    print("pip install aiohttp")
    print("Install instructions here:")
    print("https://docs.aiohttp.org/en/stable/")
    print("")
    os._exit(-1)


try:
    import board
    import busio
    import adafruit_mprls
except:
    print("")
    print("You don't have adafruit libs installed, you need that")
    print("sudo pip3 install adafruit-circuitpython-mprls")
    print("Install instructions here:")
    print("https://learn.adafruit.com/adafruit-mprls-ported-pressure-sensor-breakout?view=all")
    print("")
    os._exit(-1)


#####################################################################
# Utl
#####################################################################

def SetTimeoutInterval(secs, fn):
    def Function():
        fn()
        SetTimeoutInterval(secs, fn)

    asyncio.get_running_loop().call_later(secs, Function)

def SetTimeout(secs, fn):
    asyncio.get_running_loop().call_later(secs, fn)

def IncrRandomClamp(valNow, uniLow, uniHigh, valLow, valHigh):
    val = valNow + random.uniform(uniLow, uniHigh)

    if val < valLow:
        val = valLow
    elif val > valHigh:
        val = valHigh
    
    return val


#####################################################################
# GPIO and I2C Interfacing
#####################################################################

# https://github.com/adafruit/Adafruit_CircuitPython_MPRLS/blob/main/adafruit_mprls.py
class PressureSensor:
    def __init__(self):
        self.i2c = busio.I2C(board.SCL, board.SDA)
        self.mpr = adafruit_mprls.MPRLS(self.i2c, psi_min=0, psi_max=25)
    
    def GetHpa(self):
        val = 0
        for i in range(5):
            val += self.mpr.pressure

        avg = val / 5

        return avg

    def GetPsi(self):
        hpa = self.GetHpa()
        psi = hpa / 68.947572932

        return psi


class BME280:
    def __init__(self):
        self.bus = smbus2.SMBus(1)
        self.address = 0x77

        bme280.load_calibration_params(self.bus, self.address)

    def GetValue(self):
        SAMPLE_COUNT = 5

        humPctSum = 0
        hpaSum = 0
        tempCSum = 0
        for i in range(SAMPLE_COUNT):
            sample = bme280.sample(self.bus, self.address)
            humPctSum += sample.humidity
            hpaSum    += sample.pressure
            tempCSum  += sample.temperature

        humPct = humPctSum / SAMPLE_COUNT
        hpa = hpaSum / SAMPLE_COUNT
        tempC = tempCSum / SAMPLE_COUNT

        psi = hpa / 68.947572932
        tempF = (tempC * 9.0 / 5.0) + 32

        return (humPct, psi, tempF)


class GpioController:
    def __init__(self, bcPin):
        self.pig     = pigpio.pi()
        self.bcPin   = bcPin

        # require an asserted high value to maintain high logic level
        self.pig.set_pull_up_down(self.bcPin, pigpio.PUD_DOWN)

    def GetValue(self):
        return self.pig.read(self.bcPin)

    def End(self):
        self.pig.set_pull_up_down(self.bcPin, pigpio.PUD_OFF)


class PwmController:
    def __init__(self, bcPin):
        self.pig     = pigpio.pi()
        self.bcPin   = bcPin
        self.pctLast = 0

    def GetValue(self):
        return self.pctLast

    def MoveTowardPwm(self, targetPct, stepPct):
        pctNow = self.GetValue()

        if pctNow < targetPct:
            self.SetPwmPctGradual(pctNow + stepPct)
        elif pctNow > targetPct:
            self.SetPwmPctGradual(pctNow - stepPct)
        else:
            pass

    def SetPwmPctGradual(self, pct):
        if pct < 0:
            pct = 0
        if pct > 100:
            pct = 100

        pwmDutyCycle = int(float(pct) * 255.0 / 100.0)

        # take time to change pct to ease dramatic current changes
        pwmDutyCycleLast = int(float(self.pctLast) * 255.0 / 100.0)

        pwmDutyCycleDiff = pwmDutyCycle - pwmDutyCycleLast

        incr = 0
        if pwmDutyCycleDiff < 0:
            incr = -1
        else:
            incr = 1

        pwmDutyCycleTmp = pwmDutyCycleLast

        while pwmDutyCycleTmp != pwmDutyCycle:
            self.pig.set_PWM_dutycycle(self.bcPin, pwmDutyCycleTmp)
            time.sleep(0.002)

            pwmDutyCycleTmp += incr
        self.pig.set_PWM_dutycycle(self.bcPin, pwmDutyCycleTmp)

        # remember for next time
        self.pctLast = pct

    def End(self):
        self.pig.set_PWM_dutycycle(self.bcPin, 0)

        self.pig.stop()


#####################################################################
# Application
#####################################################################

class Application():
    def __init__(self, bcPinPwm, bcPinLimit):
        self.pwmVal = 80
        self.pwm = PwmController(bcPinPwm)
        self.limit = GpioController(bcPinLimit)
        self.status = "stopped"
        self.stopReason = "not started yet"
        self.direction = "up"
        self.psiHigh = 0.2
        self.psiLow = 0.1
        self.psiAbs = 14.5
        self.psiBaseline = self.psiAbs
        self.psi = 0.0
        self.pSensor = PressureSensor()
        self.bme280 = BME280()
        self.psiAbsExt = self.psiAbs
        self.psiBaselineExt = self.psiAbsExt
        self.tempF = 72
        self.humPct = 50

    async def Start(self, app):
        SetTimeoutInterval(0.2, self.OnTimeout)

        def Banner():
            print("")
            print("")
            print("")
            print("Application running, target browser to:")
            print(f"http://{socket.gethostname()}:8080/index.html")
            print("")
            print("")
            print("")

        SetTimeout(0.2, Banner)

    async def Stop(self, app):
        self.pwm.End()
        self.limit.End()

    def BalloonInflateStart(self):
        self.status = "running"

    def BalloonInflateStop(self):
        self.status = "stopped"

    def OnGet(self, name):
        if name == "data":
            return {
                "status": self.status,
                "stopReason": self.stopReason,
                "pwm": self.pwmVal,
                "pwmUsed": self.pwm.GetValue(),
                "psiBaseline": self.psiBaseline,
                "psiBaselineExt": self.psiBaselineExt,
                "psiHigh": self.psiHigh,
                "psiLow": self.psiLow,
                "psiAbs": self.psiAbs,
                "psi": self.psi,
                "psiAbsExt": self.psiAbsExt,
                "tempF": self.tempF,
                "humPct": self.humPct,
            }
        else:
            return {}

    def OnSet(self, name, value):
        if name == "snapshotPsiBaseline":
            self.psiBaseline = float(value)
        if name == "snapshotPsiBaselineExt":
            self.psiBaselineExt = float(value)
        if name == "pwm":
            self.pwmVal = int(value)
        elif name == "run":
            if value == "true":
                self.BalloonInflateStart()
            else:
                self.BalloonInflateStop()
                self.stopReason = "user"
        elif name == "psiHigh":
            self.psiHigh = float(value)
        elif name == "psiLow":
            self.psiLow = float(value)
        elif name == "psi":
            self.psi = float(value)

    def OnTimeout(self):
        PCT_STEP = 2

        self.psiAbs = self.pSensor.GetPsi()
        self.humPct, self.psiAbsExt, self.tempF = self.bme280.GetValue()
        self.psi = (self.psiAbs - self.psiBaseline) - (self.psiAbsExt - self.psiBaselineExt)

        if self.status == "running":
            limitHit = not self.limit.GetValue()
            if limitHit:
                self.BalloonInflateStop()
                self.stopReason = "limit"
            elif self.direction == "up":
                if self.psi <= self.psiLow:
                    self.pwm.MoveTowardPwm(100, PCT_STEP)
                elif self.psi >= self.psiHigh:
                    self.direction = "down"
                    self.pwm.MoveTowardPwm(0, PCT_STEP)
                else:
                    self.pwm.MoveTowardPwm(self.pwmVal, PCT_STEP)
            else:
                if self.psi <= self.psiLow:
                    self.direction = "up"
                    self.pwm.MoveTowardPwm(100, PCT_STEP)
                else:
                    self.pwm.MoveTowardPwm(0, PCT_STEP)
        else:
            self.direction = "up"
            self.pwm.MoveTowardPwm(0, PCT_STEP)


#####################################################################
# Web UI
# https://docs.aiohttp.org/en/stable/web_advanced.html
#####################################################################

class WebApplication():
    def __init__(self, mainApp):
        self.webApp = web.Application()
        self.webApp.add_routes([
            web.get('/get/{name}', self.OnGet),
            web.get('/set/{name}/{value}', self.OnSet),
            web.static('/', "./", show_index=True),
        ])

        self.mainApp = mainApp
        self.webApp.on_startup.append(self.mainApp.Start)
        self.webApp.on_cleanup.append(self.mainApp.Stop)

    def Start(self):
        web.run_app(self.webApp)


    async def OnGet(self, request):
        name = request.match_info.get('name')

        obj = self.mainApp.OnGet(name)

        return web.json_response(obj)

    async def OnSet(self, request):
        name = request.match_info.get('name')
        value = request.match_info.get('value')

        self.mainApp.OnSet(name, value)

        return web.json_response({})


#####################################################################
# Startup
#####################################################################

def Main():
    if len(sys.argv) != 3:
        print("Usage: " + sys.argv[0] + " <bcPinPwm> <bcPinLimit>")
        sys.exit(-1)

    bcPinPwm = int(sys.argv[1])
    bcPinLimit = int(sys.argv[2])
    mainApp = Application(bcPinPwm, bcPinLimit)

    webApp = WebApplication(mainApp)

    webApp.Start()


Main()