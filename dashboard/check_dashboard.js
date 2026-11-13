// Runs dashboard/index.html in jsdom with real Pyodide behind loadPyodide,
// pastes each case into the page, presses "Compute reliability", and prints
// what the page shows. tests/test_dashboard.py compares that with the Python
// package. Needs jsdom and pyodide:  npm install jsdom pyodide@0.26.1
//     node dashboard/check_dashboard.js dashboard/index.html cases.json
const { JSDOM } = require("jsdom");
const { loadPyodide } = require("pyodide");
const fs = require("fs");

// The page loads Pyodide and its fonts from the internet. Here Pyodide comes
// from node_modules instead, and the fonts are not needed.
const html = fs.readFileSync(process.argv[2], "utf8")
  .replace(/<script src="https:\/\/cdn\.jsdelivr\.net[^>]*><\/script>/, "")
  .replace(/<link[^>]*fonts\.(googleapis|gstatic)[^>]*>/g, "");
const cases = JSON.parse(fs.readFileSync(process.argv[3], "utf8"));

(async () => {
  const py = await loadPyodide();
  const errors = [];
  const dom = new JSDOM(html, { runScripts: "dangerously", pretendToBeVisual: true,
    beforeParse(w) { w.loadPyodide = async () => py; } });
  const w = dom.window, d = w.document;
  w.addEventListener("error", e => errors.push(e.message));
  w.console.error = (...a) => errors.push(a.join(" "));
  const wait = ms => new Promise(r => setTimeout(r, ms));
  const button = () => d.getElementById("compute-btn");
  for (let i = 0; i < 600 && (!button() || button().disabled); i++) await wait(50);
  if (!button() || button().disabled) throw new Error("the page never finished loading Python");

  const out = [];
  for (const c of cases) {
    if (c.csv !== null) d.getElementById("csv-input").value = c.csv;
    ["stat-kappa", "stat-ac1", "stat-pabak", "stat-n"].forEach(id => { d.getElementById(id).textContent = ""; });
    button().click();
    await wait(300);
    const t = id => d.getElementById(id).textContent;
    out.push({ name: c.name, kappa: t("stat-kappa"), ac1: t("stat-ac1"), pabak: t("stat-pabak"),
               n: t("stat-n"), status: d.getElementById("status-msg").textContent,
               svg: !!d.querySelector("#matrix-svg svg") });
  }
  process.stdout.write(JSON.stringify({ out, errors }));
})().catch(e => { console.error(e); process.exit(1); });
