// UI for the spend policy demo. All policy logic lives in policy.mjs.
import { RULES, evaluate } from "./policy.mjs";

const S = {
  settled: 0,
  reserved: 0,
  decisions: 0,
  denied: 0,
  prevented: 0,
  approvals: [],
  feed: [],
  history: [],
  bench: 0,
};

const money = (n) => n.toFixed(2);
const hhmm = (d) => d.toTimeString().slice(0, 5);
const $ = (id) => document.getElementById(id);
const available = () => RULES.budget - S.settled - S.reserved;

function decide(intent) {
  const d = new Date();
  const { verdict, rule } = evaluate(intent, {
    hour: d.getHours(),
    available: available(),
    history: S.history,
  });
  S.decisions += 1;

  if (verdict === "allow" || verdict === "pending") {
    S.reserved += intent.amount;
    S.history.push({ ...intent, at: d });
  }
  if (verdict === "deny") {
    S.denied += 1;
    S.prevented += intent.amount;
  }
  if (verdict === "allow") {
    setTimeout(() => {
      S.reserved -= intent.amount;
      S.settled += intent.amount;
      render();
    }, 1500);
  }

  S.feed.unshift({ ...intent, verdict, rule, at: d });
  if (verdict === "pending") {
    S.approvals.unshift({
      id: Math.random().toString(36).slice(2, 10),
      ...intent,
      rule,
    });
  }
  render();
}

function approve(id) {
  const i = S.approvals.findIndex((a) => a.id === id);
  if (i < 0) return;
  const a = S.approvals.splice(i, 1)[0];
  S.reserved -= a.amount;
  S.settled += a.amount;
  S.feed.unshift({ ...a, verdict: "allow", rule: "approved by human", at: new Date() });
  render();
}

function reject(id) {
  const i = S.approvals.findIndex((a) => a.id === id);
  if (i < 0) return;
  const a = S.approvals.splice(i, 1)[0];
  S.reserved -= a.amount;
  S.denied += 1;
  S.prevented += a.amount;
  S.feed.unshift({ ...a, verdict: "deny", rule: "rejected by human", at: new Date() });
  render();
}

// Amortise the measurement over many runs so timer resolution does not hide it.
function bench() {
  const N = 20000;
  const history = [];
  const ctx = { hour: 12, available: RULES.budget, history };
  const t0 = performance.now();
  for (let i = 0; i < N; i += 1) evaluate({ merchant: "Staples", amount: 80 }, ctx);
  S.bench = ((performance.now() - t0) * 1000) / N;
}

function render() {
  $("avail").innerHTML = money(available()) + " <small>EUR available</small>";
  $("of").textContent = "of " + money(RULES.budget) + " daily";
  $("clock").textContent = hhmm(new Date());
  $("bSet").style.width = (S.settled / RULES.budget) * 100 + "%";
  $("bRes").style.width = (S.reserved / RULES.budget) * 100 + "%";
  $("lSet").textContent = money(S.settled);
  $("lRes").textContent = money(S.reserved);
  $("sDec").textContent = S.decisions;
  $("sDen").textContent = S.denied;
  $("sPre").textContent = money(S.prevented);
  $("sP95").textContent = S.bench ? S.bench.toFixed(2) : "-";
  $("alCount").textContent = RULES.allow.length + " merchants";

  $("feed").innerHTML = S.feed.length
    ? S.feed
        .slice(0, 12)
        .map(
          (r) => `
    <div class="item">
      <div class="top">
        <span class="m">${r.merchant}</span>
        <span class="tag ${r.verdict === "allow" ? "t-allow" : r.verdict === "deny" ? "t-deny" : "t-pend"}">
          ${r.verdict === "allow" ? "ALLOW" : r.verdict === "deny" ? "DENY" : "APPROVAL"}
        </span>
      </div>
      <div class="why">${money(r.amount)} EUR &middot; ${r.rule}</div>
      <div class="mono">${hhmm(r.at)}</div>
    </div>`,
        )
        .join("")
    : `<div class="empty">No decisions yet.</div>`;

  $("approvals").innerHTML = S.approvals.length
    ? S.approvals
        .map(
          (a) => `
    <div class="ap">
      <div class="top"><b>${a.merchant}</b><span class="mono">${money(a.amount)} EUR</span></div>
      <div class="why">${a.rule}. Held against budget, not yet settled.</div>
      <div class="actions">
        <button class="yes" onclick="window.approve('${a.id}')">Approve</button>
        <button class="no" onclick="window.approve('${a.id}', true)">Reject</button>
      </div>
    </div>`,
        )
        .join("")
    : `<div class="empty">Nothing waiting.</div>`;
}

const PRESETS = [
  ["Coffee, 4.50", "Blue Bottle", 4.5],
  ["Flight, 620", "United Airlines", 620],
  ["Groceries, 85", "Whole Foods", 85],
  ["Notion, 149", "Notion", 149],
  ["Burst: 5 x 80", "Staples", 80, 5],
  ["Crypto, 40", "Coinbase", 40],
];

$("presets").innerHTML = PRESETS.map(
  (p, i) =>
    `<button class="agent" onclick="window.run(${i})"><b>${p[0]}</b><span>${p[1]} &middot; ${p[2]} EUR</span></button>`,
).join("");

window.run = (i) => {
  const p = PRESETS[i];
  const n = p[3] || 1;
  for (let k = 0; k < n; k += 1) {
    setTimeout(() => decide({ merchant: p[1], amount: p[2], category: "auto" }), k * 40);
  }
};
window.approve = (id, isReject = false) => (isReject ? reject(id) : approve(id));
window.sendIntent = () =>
  decide({
    merchant: $("m").value.trim() || "Staples",
    amount: parseFloat($("a").value) || 0,
    category: $("c").value,
  });

bench();
render();

// Seed a representative run so the first screen is not empty.
setTimeout(() => {
  decide({ merchant: "Blue Bottle", amount: 4.5, category: "food" });
  decide({ merchant: "United Airlines", amount: 620, category: "travel" });
  decide({ merchant: "Notion", amount: 149, category: "software" });
}, 250);
setTimeout(() => {
  for (let k = 0; k < 5; k += 1) {
    setTimeout(() => decide({ merchant: "Staples", amount: 80, category: "office" }), k * 40);
  }
}, 700);
