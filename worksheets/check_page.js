// Drives worksheets/index.html in jsdom and fails loudly if anything a
// teacher would do breaks. Needs jsdom:  npm install jsdom
//     node worksheets/check_page.js worksheets/index.html
const { JSDOM } = require("jsdom");
const fs = require("fs");
const assert = require("assert");

const html = fs.readFileSync(process.argv[2] || __dirname + "/index.html", "utf8");
const scriptErrors = [];
const dom = new JSDOM(html, { runScripts: "dangerously", pretendToBeVisual: true,
  url: "https://example.org/worksheets/#set=4821&n=4&context=personal,societal" });
const w = dom.window, d = w.document;
w.addEventListener("error", e => scriptErrors.push(e.message));
w.print = () => {};

setTimeout(() => {
  // the shared address opens the right set
  assert.strictEqual(d.getElementById("set-no").value, "4821");
  assert.strictEqual(d.querySelectorAll("#view-booklet .unit").length, 4);
  assert.ok(d.querySelector('input[name=context][value=personal]').checked);
  const contexts = [...d.querySelectorAll("#view-key .unit .hint")].map(p => p.textContent);
  assert.ok(contexts.every(t => /Personal|Societal/.test(t)), "filters ignored");

  // the booklet gives nothing away, the key explains every kind of mistake
  const booklet = d.getElementById("view-booklet").textContent;
  assert.ok(!/Confabulation|Interference|Full credit/.test(booklet), "booklet leaks the key");
  ["Recall Failure", "Partial Knowledge", "Confabulation", "Interference"].forEach(n =>
    assert.ok(d.getElementById("view-key").textContent.includes(n)));

  // tabs switch views
  d.querySelector('nav.tabs button[data-view="key"]').click();
  assert.ok(!d.getElementById("view-key").hidden && d.getElementById("view-booklet").hidden);

  // enter two children, leave the rest blank, score
  const rows = d.querySelectorAll("#grid tbody tr");
  assert.strictEqual(rows.length, 10);
  const fill = (tr, pick) => tr.querySelectorAll("[data-q]").forEach(el => {
    el.value = el.tagName === "SELECT" ? pick(el) : "TFT".slice(0, el.maxLength);
  });
  fill(rows[0], el => el.options[1].value);
  fill(rows[1], el => el.options[el.options.length - 1].value);
  d.getElementById("score").click();
  const report = d.getElementById("view-report");
  assert.ok(!report.hidden, "report view not shown");
  assert.ok(/2 students/.test(report.textContent), "blank rows were not skipped");
  assert.ok(report.querySelector(".reteach"), "no misconceptions listed");

  // a bad cell names the child and the question
  const textCell = rows[2].querySelector("input[data-q]");
  if (textCell) {
    textCell.value = "XYZ";
    d.getElementById("score").click();
    assert.ok(/student S03, Q\d+\.\d+/.test(d.getElementById("answer-error").textContent));
  }

  // filters that match nothing explain themselves
  d.querySelectorAll("input[name=context]").forEach(i => { i.checked = false; });
  d.querySelector('input[name=content][value=quantity]').checked = true;
  d.querySelector('input[name=context][value=scientific]').checked = true;
  d.getElementById("make").click();
  assert.ok(/No unit matches/.test(d.getElementById("setup-error").textContent));

  assert.deepStrictEqual(scriptErrors, []);
  console.log("page check passed");
}, 300);
