server_ip = 'https://10.0.1.23'

colors = [
  "#FFFFFF",
  "#E4E4E4",
  "#888888",
  "#222222",
  "#FFA7D1",
  "#E50000",
  "#E59500",
  "#A06A42",
  "#E5D900",
  "#94E044",
  "#02BE01",
  "#00D3DD",
  "#0083C7",
  "#0000EA",
  "#CF6EE4",
  "#820080",
];

chars = [
  "a",
  "b",
  "c",
  "d",
  "e",
  "f",
  "g",
  "h",
  "i",
  "j",
  "k",
  "l",
  "m",
  "n",
  "o",
  "p",
];

function start() {
  display_div = document.createElement("div");
  display_div.id = "display";
  document.body.appendChild(display_div);

  button = document.getElementById("start_button");
  button.remove();

  display_div = document.getElementById("display");

  for (let id = 0; id < 10000; id++) {
    new_div = document.createElement("div");
    //rand_color = Math.floor(Math.random() * 16777215).toString(16);
    //color_string = "#" + rand_color;
    //new_div.style.backgroundColor = color_string;
    new_div.className = "pixel";
    new_div.id = id;
    display_div.appendChild(new_div);
  }

  picture = document.createElement('img');
  picture.src = "static/colors.png"
  document.body.appendChild(picture)
  update();
}

async function fetch_data() {
  const url =server_ip+"/get_pixels";
  const response = await fetch(url);
  fetched_data = await response.text();
  return fetched_data;
}

raw_pixels = "";
function update() {
  raw_pixels = "";

    fetch_data().then((result) => {
      // Process the result here
      raw_pixels = result;
    });

  
  setTimeout(function() {
    //console.log(raw_pixels);
    //raw_pixels = raw_pixels.replaceAll('\n')
    pixels = document.getElementsByClassName('pixel');
    for (let index = 0; index < 10000; index++) {
      pixels[index].style.backgroundColor = colors[chars.indexOf(raw_pixels[index])]
    }
    raw_pixels = ""
  }, 5000);
  setTimeout(update, 10000);
}
