#!/bin/python3
from flask import Flask, request
from flask_cors import CORS
import netifaces as ni
import os
import pickle
import threading
import time
import websockets
import asyncio

size = 100

pixels = [[0 for i in range(size)] for j in range(size)]

chars = ["a", "b", "c", "d", "e", "f", "g", "h", "i", "j", "k", "l", "m", "n", "o", "p"]

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

class logger:
    logs = []
    file = "logs.txt"
    use = True

    def init():
        if not logger.use:
            return
        if not os.path.isfile(logger.file):
            with open(logger.file, "w") as f:
                f.write("")

    def log(msg):
        if not logger.use:
            return
        logger.logs.append(msg)

    def save_logs():
        if not logger.use:
            return
        with open(logger.file, "a") as f:
            for log in logger.logs:
                f.write(f"{log}\n")
            logger.logs = []

    def background_func():
        while True:
            time.sleep(10)  # 10 secs
            logger.save_logs()


class backup:
    def init():
        if os.path.isfile("save.txt"):
            backup.load()
        else:
            backup.save()

    def save():
        global pixels
        with open("save.txt", "wb") as f:
            pickle.dump(pixels, f)

    def load():
        global pixels
        with open("save.txt", "rb") as f:
            pixels = pickle.load(f)


class server:
    port = 8000

    def getIp():
        try:
            interfaces = ni.interfaces()
            for interface in interfaces:
                if interface != "lo":
                    iface_details = ni.ifaddresses(interface)
                    if ni.AF_INET in iface_details:
                        ip = iface_details[ni.AF_INET][0]["addr"]
                        return ip
            return None
        except KeyboardInterrupt:
            exit()

    local_ip = getIp()

    def loop():
        app.static_folder = "static"
        app.run(host="0.0.0.0", port=server.port, debug=False)

    def edit_script():
        with open("static/script.js", "r") as file:
            lines = file.readlines()

        lines[0] = f"server_ip = '{server.local_ip}'\n"
        lines[1] = f"port = {server.port}\n"
        lines[2] = f"ws_port = {ws.port}\n"
        lines[3] = f"size = {size}\n"

        with open("static/script.js", "w") as file:
            file.writelines(lines)

        with open("static/style.css", "r") as file:
            lines = file.readlines()

        lines[1] = f"  --size: {size};\n"

        with open("static/style.css", "w") as file:
            file.writelines(lines)

    def handle_cmd(data_in):
        try:
            data = data_in.strip().split()
            # data = ["elks", "paint", "41", "38", "blue"]
            # print(data)

            if data[1] == "fill":
                if not data[2] in colors:
                    return "wrong color"

                logger.log(f"{data[0]} {data[1]} {data[2]}")

                for y in range(size):
                    for x in range(size):
                        pixels[x][y] = int(colors.index(data[2]))

            elif data[1] == "paint":
                if not data[4] in colors:
                    return "wrong color"

                elif (
                    int(data[2]) > size
                    or int(data[2]) < 0
                    or int(data[3]) > size
                    or int(data[3]) < 0
                ):
                    return "out of bounds"

                logger.log(f"{data[0]} {data[1]} {data[2]} {data[3]} {data[4]}")

                pixels[int(data[2])][int(data[3])] = int(colors.index(data[4]))
            else:
                return "wrong cmd"

            return "pass"
        except KeyboardInterrupt:
            exit()
        except:
            return "failed"


class ws:
    port = 8001

    async def handler(websocket, path):
        try:
            data = await websocket.recv()
            if data == "get_pixels":
                backup.save()
                response = "data:"
                for y in range(100):
                    for x in range(100):
                        response = response + str(chars[pixels[x][y]])
                await websocket.send(response)
                return

            server.handle_cmd(data)
        except KeyboardInterrupt:
            exit()
        # dont care about exceptions
        except websockets.exceptions.ConnectionClosedOK:
            return
        except websockets.exceptions.ConnectionClosedError:
            return
        except websockets.exceptions.ConnectionClosed:
            return




app = Flask(__name__)
CORS(app)


@app.route("/", methods=["GET"])
def main_page_response():
    with open("static/index.htm") as index_file:
        return index_file.read()


if __name__ == "__main__":
    backup.init()
    logger.init()
    server.edit_script()

    t1 = threading.Thread(target=logger.background_func)
    t1.start()

    t2 = threading.Thread(target=server.loop)
    t2.start()

    start_server = websockets.serve(ws.handler, "0.0.0.0", ws.port)
    asyncio.get_event_loop().run_until_complete(start_server)
    asyncio.get_event_loop().run_forever()
