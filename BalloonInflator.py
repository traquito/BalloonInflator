#!/usr/bin/env -S python -u

import os
import re
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
    def __init__(self, bcPin):
        self.pwm = PwmController(bcPin)
        self.status = "stopped"
        self.psiHigh = 0.2
        self.psiLow = 0.1

    async def Start(self, app):
        SetTimeoutInterval(1, self.OnTimeout)

    async def Stop(self, app):
        self.pwm.End()

    def BalloonInflateStart(self):
        self.status = "running"

    def BalloonInflateStop(self):
        self.status = "stopped"

    def OnGet(self, name):
        if name == "data":
            return {
                "status": self.status,
                "pwm": self.pwm.GetValue(),
                "psiHigh": self.psiHigh,
                "psiLow": self.psiLow,
            }
        else:
            return {}

    def OnSet(self, name, value):
        print(f"OnSet: {name}, {value}")
        if name == "pwm":
            self.pwm.SetPwmPctGradual(int(value))
        elif name == "run":
            if value == "true":
                self.BalloonInflateStart()
            else:
                self.BalloonInflateStop()
        elif name == "psiHigh":
            self.psiHigh = float(value)
        elif name == "psiLow":
            self.psiLow = float(value)


    def OnTimeout(self):
        pass


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
    if len(sys.argv) != 2:
        print("Usage: " + sys.argv[0] + " <bcPin>")
        sys.exit(-1)

    bcPin = int(sys.argv[1])
    mainApp = Application(bcPin)

    webApp = WebApplication(mainApp)

    webApp.Start()


Main()