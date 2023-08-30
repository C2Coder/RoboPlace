 /**
 * A lib for sending data to roboplace (github.com/c2coder/RoboPlace)
 */

 import * as radio from "simpleradio"

 export let name = "ELKS"
 
 export const WHITE      = "white"
 export const PLATINUM   = "platinum"
 export const GREY       = "grey"
 export const BLACK      = "black"
 export const PINK       = "pink"
 export const RED        = "red"
 export const ORANGE     = "orange"
 export const BROWN      = "brown"
 export const YELLOW     = "yellow"
 export const LIME       = "lime"
 export const GREEM      = "green"
 export const CYAN       = "cyan"
 export const LBLUE      = "lblue"
 export const BLUE       = "blue"
 export const MAUVE      = "mauve"
 export const PURPLE     = "purple"
 
 
 export function set_name(_name:string){
     name = _name.substring(0, 9);
     if(name.length > 9){
         name = name.substring(0, 9);
     }
 }
 
 export function send(_cmd:string){
     console.log(`|${name} ${_cmd}|`)
 }
 
 export function begin(_group:number){
     radio.begin(_group);
 }
 
 export function send_radio(_cmd:string){
     radio.sendString(`${name} ${_cmd}`)
 }