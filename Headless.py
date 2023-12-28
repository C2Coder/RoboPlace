#!/bin/python3

import time
import schedule
import jacserial
import sys
import requests
import asyncio
import math
import websockets

size = 100

#server_ip = 'roboplace.vercel.app'
server_ip = '10.0.1.30'


try:
    port = sys.argv[1]
    mode = sys.argv[2]
except:
    print()
    print(f'Usage python3 Headles.py <port> <Jaculus or Normal>')
    print()
    print(f'Example: python3 Headles.py COM26 Normal')
    print(f'Example: python3 Headles.py /dev/ttyACM0 Jaculus')
    print()
    exit()

ser = jacserial.Serial(port, 115200, timeout=1)

start_time = math.floor(time.time())

timeouts = {}
timeout = 5 # seconds

chars = ["a", "b", "c", "d", "e", "f", "g", "h",
         "i", "j", "k", "l", "m", "n", "o", "p",]
colors = [

    "white",
        "platinum",
        "grey",
        "black",
        "pink",
        "red",
        "orange",
        "brown",
        "yellow",
        "lime",
        "green",
        "cyan",
        "lblue",
        "blue",
        "mauve",
        "purple"
]

class ws:
    port = 8001
    async def send_cmd(cmd):
        url = f"ws://{server_ip}:{ws.port}"
        async with websockets.connect(url) as webs:
            # Send a greeting message
            await webs.send(cmd)
    async def get_pixels():
        url = f"ws://{server_ip}:{ws.port}"
        async with websockets.connect(url) as webs:
            # Send a greeting message
            await webs.send("get_pixels")
            msg = await webs.recv()
            return msg
def reader():
    global ser

    while True:
        # read serial
        if mode == "Jaculus":
            line = ser.readline_jac()
        elif mode == "Normal":
            line = ser.readline()
        if len(line) == 0:
            break  # break from loop
        toks = parse(line)
        if toks is None:
            continue  # next loop
        handle_cmds(toks)

def parse(input):
    data = input.split(" ")
    if len(data) < 2:
        return None
    return data


def handle_cmds(toks):
    global timeouts, colors, start_time
    
    if len(toks) < 2:
        return
    #   toks[0]  toks[1] toks[2] toks[3] toks[4]
    #    80001    paint    10      10      red
    user_id = toks[0]
    cmd = toks[1]

    # Handle timeouts
    if user_id in timeouts and user_id != "elks":
    # if user_id in timeouts:
        return
    else:
        timeouts[user_id] = math.floor(time.time() - start_time)
    try:
        if cmd == 'paint':
            if toks[4] not in colors:
                print(f'{user_id} >>> {toks[1]} {toks[2]} {toks[3]} {toks[4].lower()} (WRONG COLOR)')
                return
            elif int(toks[2]) >= size or int(toks[3]) >= size:
                print(f'{user_id} >>> {toks[1]} {toks[2]} {toks[3]} {toks[4].lower()} (OUT OF LIMITS)')
                return
            else:
                print(f'{user_id} >>> {toks[1]} {toks[2]} {toks[3]} {toks[4].lower()}')

        elif cmd == 'test':
            print(f'{user_id} >>> {toks[1]}')
            return

        toks[4] = toks[4].lower()
        send_change(toks)
    except KeyboardInterrupt:
        return

def timeout_handler():
    global timeouts,timeout,  start_time
    cur_time = math.floor(time.time()-start_time)
    #print(cur_time)
    for id in list(timeouts.keys()):
        if timeouts[id] <= cur_time - timeout:
            timeouts.pop(id)
            #print("Removed: " + id)


def send_change(toks):
    data = f"{toks[0]} {toks[1]} {toks[2]} {toks[3]} {toks[4]}"
    asyncio.get_event_loop().run_until_complete(ws.send_cmd(data))


schedule.every(0.2).seconds.do(reader)
schedule.every(2).seconds.do(timeout_handler)


while True:
    schedule.run_pending()
    time.sleep(0.2)
