server_ip = 'http://10.0.1.30:8000'
size = 100

raw_pixels = "";

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
  var button = document.getElementById("start_button");
  button.remove();

  var display_div = document.createElement("div");
  display_div.id = "display";
  document.body.appendChild(display_div);

  var canvas = document.createElement("canvas");
  canvas.id = "canvas";
  canvas.width = size * 10;
  canvas.height = size * 10;

  display_div.appendChild(canvas);

  picture = document.createElement("img");
  picture.src = "static/colors.png";
  document.body.appendChild(picture);
  update();
}

async function fetch_data() {
  const url = server_ip + "/get_pixels";
  const response = await fetch(url);
  fetched_data = await response.text();
  return fetched_data;
}

function draw_on_display(raw_pixels) {
  var c = document.getElementById("canvas");
  var ctx = c.getContext("2d");

  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      ctx.fillStyle = colors[chars.indexOf(raw_pixels[y * size + x])];
      ctx.fillRect(x * 10, y * 10, 10, 10);
      ctx.stroke();
    }
  }
}

function update() {
  fetch_data().then((result) => {
    draw_on_display(result)
  });

  setTimeout(update, 10000);
}
