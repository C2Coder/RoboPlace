from flask import Flask, request
from flask_cors import CORS
import os
import pickle
import socket

# auto setup script.js
local_ip = socket.gethostbyname(socket.gethostname())
port = 8000

pixels = [[0 for i in range(100)] for j in range(100)]

def save_pixels():
    global pixels
    f = open("save.txt", "wb")
    pickle.dump(pixels, f)
    f.close()

def load_pixels():
    global pixels
    f = open("save.txt", "rb")
    pixels = pickle.load(f)


with open("static/script.js", 'r') as file:
    lines = file.readlines()

lines[0] = "server_ip = 'https://" + str(local_ip) + ":" + str(port) + "'\n"

with open("static/script.js", 'w') as file:
    file.writelines(lines)


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


@app.route('/error', methods=['GET'])
def error_response():
    return error_msg

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
    global pixels, error_msg
    if request.method == 'POST':
        # Handle POST request
        try:
            data_in = str(request.get_json()).removeprefix("b")
            #print(data_in)
            data_raw = data_in.replace("{", "").replace("}", "").replace("'", "").replace(":", "_").replace(" ", "")
            #print(data_raw)
            data = data_raw.split("_")
            if data[0] == "fill":
                if not data[1] in colors:
                    return "wrong color"

                for y in range(100):
                    for x in range(100):
                        pixels[x][y] = int(colors.index(data[1]))

                return "gut"

            else:
                if not data[2] in colors:
                    return "wrong color"
                
                pixels[int(data[0])][int(data[1])] = int(colors.index(data[2]))
            return "gut" # idk why, but this was the first thing that came to mind
        except:
            return "failed"


if __name__ == '__main__':
    app.static_folder = "static"
    app.run(host="0.0.0.0", port=port)

