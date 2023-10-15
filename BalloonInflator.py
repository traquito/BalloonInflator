#!/usr/bin/env -S python3 -u

import os
import re
import random
import sys
import time
import asyncio

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


#####################################################################
# Utl
#####################################################################

def SetTimeoutInterval(secs, fn):
    def Function():
        fn()
        SetTimeoutInterval(secs, fn)

    asyncio.get_running_loop().call_later(secs, Function)


#####################################################################
# GPIO Control
#####################################################################

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
        self.psi = 0.0

    async def Start(self, app):
        SetTimeoutInterval(1, self.OnTimeout)

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
                "psiHigh": self.psiHigh,
                "psiLow": self.psiLow,
                "psi": self.psi
            }
        else:
            return {}

    def OnSet(self, name, value):
        # print(f"OnSet: {name}, {value}")

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
        if self.status == "running":
            limitHit = not self.limit.GetValue()
            if limitHit:
                self.BalloonInflateStop()
                self.stopReason = "limit"
            elif self.direction == "up":
                if self.psi <= self.psiLow:
                    self.pwm.SetPwmPctGradual(100)
                elif self.psi >= self.psiHigh:
                    self.direction = "down"
                    self.pwm.SetPwmPctGradual(0)
                else:
                    self.pwm.SetPwmPctGradual(self.pwmVal)
            else:
                if self.psi <= self.psiLow:
                    self.pwm.SetPwmPctGradual(100)
                    self.direction = "up"
        else:
            self.direction = "up"
            self.pwm.SetPwmPctGradual(0)


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