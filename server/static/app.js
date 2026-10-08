// ---- Fake cases (same shape as the agreed case fields) ----
// Later these come from GET /api/cases instead. Coordinates are placeholders
// until P4's areas.json is ready.
const FAKE_CASES = [
  {
    id: 1, score: 92, people_count: 6, vulnerable: true, trapped: true,
    water_level: "roof", location_text: "Near St. Mary's church, Chengannur",
    phone: "98xxxxxx01", confidence: 0.9, missing: [],
    reasons: ["Trapped on roof", "Elderly person present", "6 people"],
    lat: 9.3180, lng: 76.6110
  },
  {
    id: 2, score: 64, people_count: 3, vulnerable: false, trapped: false,
    water_level: "waist", location_text: "Aluva market road",
    phone: "98xxxxxx02", confidence: 0.8, missing: [],
    reasons: ["Water at waist level", "3 people"],
    lat: 10.1004, lng: 76.3570
  },
  {
    id: 3, score: 38, people_count: 2, vulnerable: false, trapped: false,
    water_level: "ankle", location_text: "Kakkanad, near the bus stop",
    phone: "", confidence: 0.6, missing: ["phone"],
    reasons: ["Water rising", "No phone number"],
    lat: 10.0159, lng: 76.3419
  }
];

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

drawCases(FAKE_CASES);
