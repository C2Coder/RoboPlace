#!/bin/python3

import time
import schedule
import jacserial
import sys
import requests
import math
import pygame

from pygame.locals import (
    K_ESCAPE,
    KEYDOWN,
    QUIT,
)

size = 100
window_size = 800

server_ip = 'https://roboplace.vercel.app'

port = sys.argv[1]

try:
    port = sys.argv[1]
    mode = sys.argv[2]
except:
    print()
    print(f'Usage ./Headles.py <port> <Jaculus or Normal>')
    print()
    print(f'Example: python3 RoboPlace.py COM26 Normal')
    print(f'Example: python3 RoboPlace.py /dev/ttyACM0 Jaculus')
    print()
    exit()

ser = jacserial.Serial(port, 115200, timeout=1)

start_time = math.floor(time.time())

timeouts = {}
timeout = 5  # 5 seconds

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

hex_colors = {
    "a":    pygame.Color("#FFFFFF"),
    "b":    pygame.Color("#E4E4E4"),
    "c":    pygame.Color("#888888"),
    "d":    pygame.Color("#222222"),
    "e":    pygame.Color("#FFA7D1"),
    "f":    pygame.Color("#E50000"),
    "g":    pygame.Color("#E59500"),
    "h":    pygame.Color("#A06A42"),
    "i":    pygame.Color("#E5D900"),
    "k":    pygame.Color("#94E044"),
    "k":    pygame.Color("#02BE01"),
    "l":    pygame.Color("#00D3DD"),
    "m":    pygame.Color("#0083C7"),
    "n":    pygame.Color("#0000EA"),
    "o":    pygame.Color("#CF6EE4"),
    "p":    pygame.Color("#820080")
}

pixels = [[]]
pixel_size = window_size / size


def init():
    global pixels
    screen = pygame.display.set_mode([window_size, window_size])
    pygame.init()

    pygame.display.set_caption('RoboPlace')
    pygame.font.init()

    pixels = [['a' for i in range(size)] for j in range(size)]

    
    req = requests.get(url=server_ip + '/get_pixels')
    response = req.text
    for y in range(100):
        for x in range(100):
            pixels[x][y] = response[(y*100)+x]

    draw(screen)


def draw(surface):
    for y in range(size):
        for x in range(size):
            pygame.draw.rect(
                surface, hex_colors[pixels[x][y]], (x*pixel_size, y*pixel_size, pixel_size, pixel_size))
    pygame.display.flip()


def reader():
    global ser
    if (mode == "Jaculus"):
        cmds = ser.readline_jac()
    elif (mode == "Normal"):
        cmds = ser.readline()
    else:
        print('Wrong mode')
        print('You selected => ' + mode)
        print('Options are => Jaculus or Normal')

    if len(cmds) < 5:
        return

    handle_cmds(parse(cmds))


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
    toks[4] = toks[4].lower()

    # Handle timeouts
    # if user_id in timeouts and user_id != "ELKS":
    if user_id in timeouts:
        return
    else:
        timeouts[user_id] = math.floor(time.time() - start_time)

    if cmd == 'paint':
        if toks[4] not in colors:
            print(
                f'{user_id} >>> {toks[1]} {toks[2]} {toks[3]} {toks[4]} (WRONG COLOR)')
            return
        elif int(toks[2]) >= size or int(toks[3]) >= size:
            print(
                f'{user_id} >>> {toks[1]} {toks[2]} {toks[3]} {toks[4]} (OUT OF LIMITS)')
            return
        else:
            print(f'{user_id} >>> {toks[1]} {toks[2]} {toks[3]} {toks[4]}')

    elif cmd == 'test':
        print(f'{user_id} >>> {toks[1]}')
        return

    send_change(toks[2], toks[3], toks[4])


def timeout_handler():
    global timeouts, timeout,  start_time
    cur_time = math.floor(time.time()-start_time)
    # print(cur_time)
    for id in list(timeouts.keys()):
        if timeouts[id] <= cur_time - timeout:
            timeouts.pop(id)
            # print("Removed: " + id)


def send_change(x, y, color):
    obj = {str(x) + "_" + str(y): str(color)}
    req = requests.post(url=server_ip + '/post', json=obj)

    if (req.text != "gut"):
        # fuck, something went wrong
        print("Something went wrong on the server")


schedule.every(0.2).seconds.do(reader)
schedule.every(2).seconds.do(timeout_handler)


init()

while True:
    schedule.run_pending()
    time.sleep(0.2)
