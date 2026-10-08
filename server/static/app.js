
// ---- Colour by score: red = most urgent ----
function colourFor(score) {
  if (score >= 80) return "#c8102e";
  if (score >= 50) return "#e87722";
  return "#d4a017";
}

// ---- Create the map ----
const map = L.map("map").setView([9.8, 76.45], 9);

// Map tiles need internet. If they fail, the grey background and pins still show.
L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 18,
  attribution: "&copy; OpenStreetMap contributors"
}).addTo(map);

// ---- Draw pins and the queue ----
function drawCases(cases) {
  const sorted = [...cases].sort((a, b) => b.score - a.score);
  const queue = document.getElementById("queue");
  queue.innerHTML = "";

  sorted.forEach((c) => {
    const pin = L.circleMarker([c.lat, c.lng], {
      radius: 10,
      color: "#ffffff",
      weight: 2,
      fillColor: colourFor(c.score),
      fillOpacity: 1
    }).addTo(map);

    pin.bindPopup(
      `<strong>Score ${c.score}</strong><br>` +
      `${c.people_count} people, water at ${c.water_level}<br>` +
      `${c.location_text}<br>` +
      `<em>${c.reasons.join(", ")}</em>`
    );

    const item = document.createElement("li");
    item.innerHTML =
      `<span class="score" style="background:${colourFor(c.score)}">${c.score}</span>` +
      `<span>${c.location_text}</span>`;
    item.addEventListener("click", () => {
      map.setView([c.lat, c.lng], 13);
      pin.openPopup();
    });
    queue.appendChild(item);
  });
}

fetch("/api/cases")
    .then((res) => res.json())
    .then(drawCases)
    .catch(() => alert("Can't reach the ReliefRank server. Start it with python run.py"));
