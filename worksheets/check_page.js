// Drives worksheets/index.html in jsdom the way a teacher would, and fails
// loudly if anything breaks. Needs jsdom:  npm install jsdom
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
const wait = ms => new Promise(r => setTimeout(r, ms));
const $ = id => d.getElementById(id);

function fillTwo(pickRight) {
  const rows = d.querySelectorAll("#grid tbody tr");
  [0, 1].forEach(r => rows[r].querySelectorAll("[data-q]").forEach(el => {
    el.value = el.tagName === "SELECT" ? el.options[pickRight ? 1 : el.options.length - 1].value
                                       : "TFT".slice(0, el.maxLength);
  }));
  return rows;
}

(async () => {
  await wait(300);
  // the shared address opens the right set, with the right filters
  assert.strictEqual($("set-no").value, "4821");
  assert.strictEqual(d.querySelectorAll("#view-booklet .unit").length, 4);
  assert.ok(d.querySelector("input[name=context][value=personal]").checked);
  const contexts = [...d.querySelectorAll("#view-key .unit .hint")].map(p => p.textContent);
  assert.ok(contexts.every(t => /Personal|Societal/.test(t)), "filters ignored");

  // the booklet gives nothing away, the key explains every kind of mistake
  assert.ok(!/Confabulation|Interference|Full credit/.test($("view-booklet").textContent), "booklet leaks the key");
  ["Recall Failure", "Partial Knowledge", "Confabulation", "Interference"].forEach(n =>
    assert.ok($("view-key").textContent.includes(n)));

  // tabs switch views
  d.querySelector('nav.tabs button[data-view="key"]').click();
  assert.ok(!$("view-key").hidden && $("view-booklet").hidden);

  // a bad cell names the child and the question
  let rows = d.querySelectorAll("#grid tbody tr");
  assert.strictEqual(rows.length, 10);
  const textCell = rows[2].querySelector("input[data-q]");
  if (textCell) {
    textCell.value = "XYZ";
    $("score").click();
    assert.ok(/student S03, Q\d+\.\d+/.test($("answer-error").textContent));
    textCell.value = "";
  }

  // round one: two children with plenty of mistakes, blank rows skipped
  const firstIds = [...d.querySelectorAll("#view-key .unit .hint")].length;
  fillTwo(false);
  $("score").click();
  const report = $("view-report");
  assert.ok(!report.hidden, "report view not shown");
  assert.ok(/2 students/.test(report.textContent), "blank rows were not skipped");
  assert.ok(report.querySelector(".reteach"), "no misconceptions listed");
  assert.ok($("follow-up"), "no follow-up button");
  const firstHash = w.location.hash;
  const firstUnits = report.ownerDocument.querySelectorAll("#view-booklet .unit h2").length;

  // follow-up set: same kinds of unit, guaranteed new numbers
  $("follow-up").click();
  await wait(200);
  assert.ok(/templates=/.test(w.location.hash) && /from=/.test(w.location.hash));
  assert.ok(/Follow-up set/.test($("share-line").textContent), "share line does not say follow-up");
  const followTitles = [...d.querySelectorAll("#view-booklet .unit h2")].map(h => h.textContent);
  assert.ok(followTitles.length >= 1 && followTitles.length <= 4);
  const params = new w.URLSearchParams(w.location.hash.slice(1));
  assert.strictEqual(params.get("from"), firstHash.slice(1));
  assert.ok(firstUnits === 4 && firstIds === 4);

  // round two: fewer mistakes, and the report compares the rounds by itself
  fillTwo(true);
  $("score").click();
  await wait(50);
  const box = $("compare-box");
  assert.ok(/Compared with the first round/.test(box.textContent), "no comparison shown");
  assert.ok(box.querySelector("table"), "comparison has no table");

  // filters that match nothing explain themselves
  d.querySelectorAll("input[name=context]").forEach(i => { i.checked = false; });
  d.querySelector("input[name=content][value=quantity]").checked = true;
  d.querySelector("input[name=context][value=scientific]").checked = true;
  $("make").click();
  assert.ok(/No unit matches/.test($("setup-error").textContent));

  assert.deepStrictEqual(scriptErrors, []);
  await hindi();
  console.log("page check passed");
})().catch(e => { console.error(e); process.exit(1); });

// The same journey in Hindi, plus switching language halfway through.
async function hindi() {
  const errors = [];
  const hd = new JSDOM(html, { runScripts: "dangerously", pretendToBeVisual: true,
    url: "https://example.org/worksheets/#set=4821&n=4&context=personal,societal&lang=hi" });
  const hw = hd.window, doc = hw.document;
  hw.addEventListener("error", e => errors.push(e.message));
  hw.print = () => {};
  const g = id => doc.getElementById(id);
  await wait(300);
  const devanagari = /[\u0900-\u097F]/;

  assert.strictEqual(doc.documentElement.lang, "hi");
  assert.ok(!g("draft-note").hidden && devanagari.test(g("draft-note").textContent), "no draft note in Hindi");
  assert.ok(devanagari.test(g("site-h1").textContent));
  const titles = [...doc.querySelectorAll("#view-booklet .unit h2")].map(h => h.textContent);
  assert.strictEqual(titles.length, 4);
  assert.ok(titles.every(t => devanagari.test(t) && !/[a-z]{4,}/.test(t)), "unit titles not in Hindi: " + titles);
  ["याद न होना", "अधूरी समझ", "पक्की गलत धारणा", "दूसरे विषय का घालमेल"].forEach(n =>
    assert.ok(g("view-key").textContent.includes(n), "key misses " + n));
  assert.ok(!/पक्की गलत धारणा|पूरे अंक:/.test(g("view-booklet").textContent), "Hindi booklet leaks the key");

  // the same set in English has the same answer letters
  const keysHi = [...doc.querySelectorAll("#view-key .key-answer")].map(x => x.textContent).filter(x => /^[A-D]$/.test(x));
  doc.querySelector('#lang-switch button[data-lang="en"]').click();
  await wait(50);
  assert.strictEqual(doc.documentElement.lang, "en");
  assert.ok(!/lang=/.test(hw.location.hash), "English address should not carry lang");
  const keysEn = [...doc.querySelectorAll("#view-key .key-answer")].map(x => x.textContent).filter(x => /^[A-D]$/.test(x));
  assert.deepStrictEqual(keysHi, keysEn, "answer letters differ between languages");

  // answers typed in English are still there after switching to Hindi
  let rows = doc.querySelectorAll("#grid tbody tr");
  const firstSelect = rows[0].querySelector("select[data-q]");
  firstSelect.value = firstSelect.options[firstSelect.options.length - 1].value;
  firstSelect.dispatchEvent(new hw.Event("change", { bubbles: true }));
  const kept = firstSelect.value;
  doc.querySelector('#lang-switch button[data-lang="hi"]').click();
  await wait(50);
  assert.ok(/lang=hi/.test(hw.location.hash));
  rows = doc.querySelectorAll("#grid tbody tr");
  assert.strictEqual(rows[0].querySelector("select[data-q]").value, kept, "answers lost on switching language");

  // a bad cell is explained in Hindi
  const textCell = rows[2].querySelector("input[data-q]");
  if (textCell) {
    textCell.value = "XYZ";
    g("score").click();
    assert.ok(/विद्यार्थी S03, Q\d+\.\d+/.test(g("answer-error").textContent), "error not in Hindi: " + g("answer-error").textContent);
    textCell.value = "";
  }

  // a Hindi report, then a Hindi follow-up and comparison
  [0, 1].forEach(r => rows[r].querySelectorAll("[data-q]").forEach(el => {
    el.value = el.tagName === "SELECT" ? el.options[el.options.length - 1].value : "TFT".slice(0, el.maxLength);
  }));
  g("score").click();
  const rep = g("view-report");
  assert.ok(/2 विद्यार्थी/.test(rep.textContent), "Hindi report summary missing");
  assert.ok(/विकल्प [A-D]|पंक्ति \d+ को|लिखित उत्तर, कोड/.test(rep.textContent), "wrong answers not described in Hindi");
  assert.ok(!/ of \d+ students|option [A-D]/.test(rep.textContent), "English left in the Hindi report");
  g("follow-up").click();
  await wait(200);
  assert.ok(/lang=hi/.test(hw.location.hash), "follow-up dropped the language");
  assert.ok(!/lang/.test(new hw.URLSearchParams(hw.location.hash.slice(1)).get("from")), "from should not carry lang");
  assert.ok(/फॉलो-अप सेट/.test(g("share-line").textContent));
  doc.querySelectorAll("#grid tbody tr").forEach((tr, i) => { if (i < 2) tr.querySelectorAll("[data-q]").forEach(el => {
    el.value = el.tagName === "SELECT" ? el.options[1].value : "TFT".slice(0, el.maxLength);
  }); });
  g("score").click();
  await wait(50);
  assert.ok(/पहले दौर से तुलना/.test(g("compare-box").textContent), "no Hindi comparison");
  assert.ok(g("compare-box").querySelector("table"));

  // nothing matches: the message is in Hindi
  doc.querySelectorAll("input[name=context]").forEach(i => { i.checked = false; });
  doc.querySelector("input[name=content][value=quantity]").checked = true;
  doc.querySelector("input[name=context][value=scientific]").checked = true;
  g("make").click();
  assert.ok(devanagari.test(g("setup-error").textContent) && !g("setup-error").hidden);
  assert.deepStrictEqual(errors, []);
}
