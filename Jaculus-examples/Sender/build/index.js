import * as gpio from "gpio";
import * as roboplace from "./libs/roboplace.js";
roboplace.begin(8);
roboplace.set_name("C2C");
console.log(roboplace.name);
gpio.pinMode(18, gpio.PinMode.INPUT_PULLUP);
gpio.on("falling", 18, () => {
    roboplace.send("paint 0 0 red");
});
