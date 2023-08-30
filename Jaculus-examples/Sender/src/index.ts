import * as gpio from "gpio";
import * as roboplace from "./libs/roboplace.js"

roboplace.begin(8); // sets up radio with group 8
roboplace.set_name("C2C");


console.log(roboplace.name);
gpio.pinMode(18, gpio.PinMode.INPUT_PULLUP);
gpio.pinMode(16, gpio.PinMode.INPUT_PULLUP);


gpio.on("falling", 18, ()=>{
    roboplace.send("paint 0 0 red");

    // roboplace.send_radio("paint 0 0 red");
    // sends the command over radio
})
gpio.on("falling", 16, ()=>{
    roboplace.send("paint 0 0 black");

    // roboplace.send_radio("paint 0 0 black");
    // sends the command over radio
})
