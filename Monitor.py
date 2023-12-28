#!/bin/python3
# ========================= LIBRARIES ========================= #
import pygame
import sys
import os
import websockets
import asyncio

# Import pygame.locals for easier access to key coordinates
# Updated to conform to flake8 and black standards
from pygame.locals import (
    K_ESCAPE,
    KEYDOWN,
    QUIT,
)

server_ip = "10.0.1.30"


class data:
    window_size = 800
    size = 100


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

# ========================= GAME class ========================= #


class Game:
    size = data.size
    window_size = data.window_size
    running = True

    def get_pixels():
        try:
            pixels = (
                asyncio.get_event_loop()
                .run_until_complete(ws.get_pixels())
                .replace("data:", "")
            )
            for y in range(100):
                for x in range(100):
                    Screen.pixels[x][y] = Screen.colors[
                        Screen.chars.index(pixels[(y * 100) + x])
                    ]
        except ConnectionRefusedError:
            pass
        except websockets.exceptions.InvalidMessage:
            pass


# ========================= SCREEN class ========================= #


class Screen:
    chars = [
        "a",
        "b",
        "c",
        "d",
        "e",
        "f",
        "g",
        "h",
        "i",
        "j",
        "k",
        "l",
        "m",
        "n",
        "o",
        "p",
    ]
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
        "purple",
    ]
    COLOR = {
        "white": pygame.Color("#FFFFFF"),
        "platinum": pygame.Color("#E4E4E4"),
        "grey": pygame.Color("#888888"),
        "black": pygame.Color("#222222"),
        "pink": pygame.Color("#FFA7D1"),
        "red": pygame.Color("#E50000"),
        "orange": pygame.Color("#E59500"),
        "brown": pygame.Color("#A06A42"),
        "yellow": pygame.Color("#E5D900"),
        "lime": pygame.Color("#94E044"),
        "green": pygame.Color("#02BE01"),
        "cyan": pygame.Color("#00D3DD"),
        "lblue": pygame.Color("#0083C7"),
        "blue": pygame.Color("#0000EA"),
        "mauve": pygame.Color("#CF6EE4"),
        "purple": pygame.Color("#820080"),
    }

    DEFAULT_COLOR = "white"

    pixels = []
    pixel_size = Game.window_size / Game.size

    def init():
        Screen.pixels = [
            [Screen.DEFAULT_COLOR for i in range(Game.size)] for j in range(Game.size)
        ]
        Game.get_pixels()

    def update(surface):
        for y in range(Game.size):
            for x in range(Game.size):
                pygame.draw.rect(
                    surface,
                    Screen.COLOR[Screen.pixels[x][y]],
                    (
                        x * Screen.pixel_size,
                        y * Screen.pixel_size,
                        Screen.pixel_size,
                        Screen.pixel_size,
                    ),
                )


# ========================= Main Loop ========================= #


def main():
    screen = pygame.display.set_mode([Game.window_size, Game.window_size])
    pygame.init()

    pygame.display.set_caption("RoboPlace Monitor")

    Screen.init()
    Screen.update(screen)
    pygame.display.flip()

    # Variable to keep the main loop running
  

    pygame.time.set_timer(pygame.USEREVENT, 1000)  # every 5s

    # serial setup

    while Game.running:
        event = pygame.event.wait()
        # Did the user hit a key?
        if event.type == KEYDOWN:
            if event.key == K_ESCAPE:
                Game.running = False
        elif event.type == QUIT:
            Game.running = False
        elif event.type == pygame.USEREVENT:
            Game.get_pixels()
            Screen.update(screen)
            pygame.display.flip()
    pygame.quit()
    exit()

if __name__ == "__main__":
    main()
