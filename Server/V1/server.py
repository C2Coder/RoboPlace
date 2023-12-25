#!/bin/python3
from flask import Flask, request
from flask_cors import CORS
import netifaces as ni
import os
import pickle

size = 10
port = 8000

def get_private_ip():
    try:
        # Get a list of all interfaces
        interfaces = ni.interfaces()

        # Iterate through interfaces to find the one that's not loopback and has an IP address
        for interface in interfaces:
            if interface != 'lo':
                iface_details = ni.ifaddresses(interface)
                if ni.AF_INET in iface_details:
                    ip = iface_details[ni.AF_INET][0]['addr']
                    return ip
        return None
    except Exception as e:
        print(f"Error: {e}")
        return None

local_ip = get_private_ip()
print(local_ip)

pixels = [[0 for i in range(size)] for j in range(size)]


def save_pixels():
    global pixels
    f = open("save.txt", "wb")
    pickle.dump(pixels, f)
    f.close()

def load_pixels():
    global pixels
    f = open("save.txt", "rb")
    pixels = pickle.load(f)


def edit_script():
    global local_ip


    with open("static/script.js", 'r') as file:
        lines = file.readlines()

    lines[0] = f"server_ip = 'http://{local_ip}:{port}'\n"
    lines[1] = f"size = {size}\n"

    with open("static/script.js", 'w') as file:
        file.writelines(lines)


        
    with open("static/style.css", 'r') as file:
        lines = file.readlines()

    lines[1] = f"  --size: {size};\n"

    with open("static/style.css", 'w') as file:
        file.writelines(lines)

edit_script()

if os.path.isfile("save.txt"):
    load_pixels()
else:
    save_pixels()

chars = ["a", "b", "c", "d", "e", "f", "g", "h",
         "i", "j", "k", "l", "m", "n", "o", "p"]

colors = ["white", "platinum", "grey", "black", "pink", "red", "orange",
          "brown", "yellow", "lime", "green", "cyan", "lblue", "blue", "mauve", "purple"]

hex_colors = ['#FFFFFF', '#E4E4E4', '#888888', '#222222', '#FFA7D1', '#E50000', '#E59500',
              '#A06A42', '#E5D900', '#94E044', '#02BE01', '#00D3DD', '#0083C7', '#0000EA', '#CF6EE4', '#820080']

app = Flask(__name__)
CORS(app)

# main page

@app.route('/', methods=['GET'])
def main_page_response():
    with open("static/index.htm") as index_file:
        return index_file.read()
    
# request handlers

@app.route('/get_pixels', methods=['GET'])
def handle_request():
    if request.method == 'GET':
        #print(dict(args))
        response = ""
        for y in range(100):
            for x in range(100):
                response = response + str(chars[pixels[x][y]])
            response = response
        return response


@app.route('/post', methods=['POST'])
def handle_incoming():
    global pixels
    if request.method == 'POST':
        try:
            data_in = str(request.get_json()).removeprefix("b").lower()
            data_raw = data_in.replace("{", "").replace("}", "").replace("'", "").replace(":", "_").replace(" ", "")
            data = data_raw.split("_")
            if data[0] == "fill":
                if not data[1] in colors:
                    return "wrong color"

                for y in range(size):
                    for x in range(size):
                        pixels[x][y] = int(colors.index(data[1]))

                return "pass"
            else:
                if not data[2] in colors:
                    return "wrong color"
                
                pixels[int(data[0])][int(data[1])] = int(colors.index(data[2]))
            return "pass"
        except:
            return "failed"


if __name__ == '__main__':
    app.static_folder = "static"
    app.run(host="0.0.0.0", port=port)

