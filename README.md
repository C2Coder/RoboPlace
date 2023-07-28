# RoboPlace_client

## Library for ELKS
- If you wanna use this code, you need a custom Jaculus library, you can find it at this repo (https://github.com/C2Coder/jacserial) under the jaculus-lib folder there is a jacserial.ts file. Just add this file to the libs folder (where is the colors.ts file) in you Jaculus project.

## How to use
- Git clone the repo
`git clone https://github.com/C2Coder/RoboPlace_client`

- Open the downloaded folder

- Install requirements 
`pip install -r requirements.txt`

- Run the app 
    - if you have a board with Jaculus connected 
    `python3 ./RoboPlaceJaculus.py <port>` and put the port that your elks is connected, on windows something like COM26
    - if you have something else, like microbit connected
    `python3 ./RoboPlaceNormal.py <port>`
- If something doesnt work, send me a message on discord (@C2Coder)
- For the people that wanna see the code that runs on the vercel server (https://github.com/RoboPlace_server_vercel)
