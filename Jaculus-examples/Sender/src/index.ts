import * as gpio from "gpio";
import * as roboplace from "./libs/roboplace.js"

roboplace.begin(8); // sets up radio with group 8
roboplace.set_name("C2C"); // sets the name/identifier so the commands are "C2C paint o o red"


console.log(roboplace.name);
gpio.pinMode(18, gpio.PinMode.INPUT_PULLUP);
gpio.pinMode(16, gpio.PinMode.INPUT_PULLUP);


gpio.on("falling", 18, ()=>{
    roboplace.send("paint 0 0 red");       // sends the command over serial
    roboplace.send_radio("paint 0 0 red"); // sends the command over radio
})

gpio.on("falling", 16, ()=>{
    roboplace.send("paint 0 0 black");       // sends the command over serial
    roboplace.send_radio("paint 0 0 black"); // sends the command over radio
})
