import * as roboplace from "./libs/roboplace.js";
import * as radio from "simpleradio";
roboplace.begin(8);
radio.on("string", (str, info) => {
    let name = str.split(" ")[0];
    roboplace.set_name(name);
    roboplace.send(str.replace(name + " ", ""));
});
