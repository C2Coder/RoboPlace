# RoboPlace_client

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