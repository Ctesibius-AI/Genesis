"""QA console dashboard — the single localhost HTML page (spec §14, D-QA-7).

A read-only instrument: fetches `/api/model` and `/api/comments`, renders the ledger of
captured episodes with the gate's verdict language, and posts bounded QA notes to
`/api/comments`. Stdlib only (a string constant) — no framework import here; `server.py`
serves `DASHBOARD_HTML` at `/`. Localhost, no auth.
"""

from __future__ import annotations

DASHBOARD_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Genesis · QA console</title>
<style>
  :root{
    --ink:#16161a; --panel:#1c1c21; --panel2:#212128; --line:#2c2c34;
    --text:#eae7df; --muted:#8c8a80; --faint:#57554e;
    --verdigris:#63b0a0; --ochre:#d6a44a; --oxblood:#c66159; --violet:#9a86c4;
    --display:"Palatino Linotype",Palatino,"Iowan Old Style","Book Antiqua",Georgia,serif;
    --mono:ui-monospace,"SF Mono",Menlo,"Roboto Mono",monospace;
    --sans:system-ui,-apple-system,"Segoe UI",sans-serif;
  }
  *{box-sizing:border-box}
  html,body{margin:0}
  body{background:var(--ink);color:var(--text);font-family:var(--sans);
    font-size:14px;line-height:1.5;-webkit-font-smoothing:antialiased}
  a{color:var(--verdigris)}
  .wrap{max-width:1240px;margin:0 auto;padding:28px 24px 64px}

  /* masthead */
  header{display:flex;align-items:flex-end;justify-content:space-between;gap:24px;
    border-bottom:1px solid var(--line);padding-bottom:18px}
  .brand{display:flex;align-items:baseline;gap:14px}
  .brand h1{font-family:var(--display);font-weight:600;font-size:40px;letter-spacing:.01em;
    margin:0;line-height:1}
  .brand .eyebrow{font-family:var(--mono);font-size:11px;letter-spacing:.28em;
    text-transform:uppercase;color:var(--verdigris)}
  .inscription{font-family:var(--display);font-style:italic;font-size:19px;color:var(--faint);
    letter-spacing:.06em;text-align:right;line-height:1.25}
  .inscription .root{display:block;font-family:var(--mono);font-style:normal;font-size:11px;
    letter-spacing:0;color:var(--faint);margin-top:6px}

  /* health strip */
  .vitals{display:grid;grid-template-columns:repeat(5,1fr);gap:1px;background:var(--line);
    border:1px solid var(--line);margin:22px 0 26px}
  .vital{background:var(--panel);padding:16px 18px}
  .vital .n{font-family:var(--mono);font-size:30px;font-variant-numeric:tabular-nums;line-height:1}
  .vital .l{font-family:var(--mono);font-size:10px;letter-spacing:.18em;text-transform:uppercase;
    color:var(--muted);margin-top:8px}
  .vital.key{background:var(--panel2)}
  .vital.key .n{color:var(--ochre)}
  .vital.alarm .n{color:var(--oxblood)}

  /* layout */
  .grid{display:grid;grid-template-columns:1.75fr 1fr;gap:26px;align-items:start}
  .colhead{font-family:var(--mono);font-size:11px;letter-spacing:.22em;text-transform:uppercase;
    color:var(--muted);margin:0 0 12px;display:flex;justify-content:space-between}
  .colhead .count{color:var(--faint)}

  /* cards / ledger */
  .card{border:1px solid var(--line);border-left:2px solid var(--faint);background:var(--panel);
    padding:14px 16px;margin-bottom:10px;cursor:pointer;transition:border-color .12s,background .12s}
  .card:hover{background:var(--panel2)}
  .card.sel{border-left-color:var(--verdigris)}
  .card .top{display:flex;align-items:center;justify-content:space-between;gap:12px}
  .eid{font-family:var(--mono);font-size:13px;color:var(--verdigris)}
  .ts{font-family:var(--mono);font-size:11px;color:var(--faint)}
  .summary{margin:9px 0 0;color:var(--text);white-space:pre-wrap;
    display:-webkit-box;-webkit-line-clamp:4;-webkit-box-orient:vertical;overflow:hidden}
  .actions{display:flex;flex-wrap:wrap;gap:6px;margin-top:11px}
  .card .caret{color:var(--faint);font-size:11px;margin-left:7px;transition:transform .12s}
  .card.expanded .caret{color:var(--verdigris);transform:rotate(90deg);display:inline-block}
  .card.expanded .summary{-webkit-line-clamp:unset;overflow:visible}
  .detail{display:none;margin-top:12px;padding-top:11px;border-top:1px solid var(--line)}
  .card.expanded .detail{display:block}
  .drow{display:flex;align-items:baseline;gap:9px;padding:5px 0;font-family:var(--mono);
    font-size:11.5px;flex-wrap:wrap}
  .drow .dk{color:var(--text)} .drow .da{color:var(--violet)}
  .drow .dr{color:var(--muted);font-family:var(--sans);flex-basis:100%}

  /* chips */
  .chip{font-family:var(--mono);font-size:10.5px;letter-spacing:.04em;padding:2px 7px;
    border:1px solid var(--line);border-radius:2px;color:var(--muted);white-space:nowrap}
  .chip.ex-no{color:var(--muted)} .chip.ex-in-progress{color:var(--ochre);border-color:#4a3f27}
  .chip.ex-done{color:var(--verdigris);border-color:#274640}
  .chip.ok{color:var(--verdigris);border-color:#274640}
  .chip.warn{color:var(--ochre);border-color:#4a3f27}
  .chip.alarm{color:var(--oxblood);border-color:#4a2c2a}
  .chip.change{color:var(--violet);border-color:#3a3350}
  .chip.sec{color:#9fb0c4;border-color:#2c3543}

  /* rail lists */
  .rail section{margin-bottom:26px}
  .row{display:flex;align-items:baseline;gap:10px;padding:7px 0;border-bottom:1px solid var(--line);
    font-family:var(--mono);font-size:12px}
  .row .rt{color:var(--faint);font-size:10.5px;margin-left:auto;white-space:nowrap}
  .empty{color:var(--faint);font-family:var(--display);font-style:italic;font-size:15px;
    border:1px dashed var(--line);padding:16px;line-height:1.45}

  /* QA notes */
  .note{border-bottom:1px solid var(--line);padding:9px 0}
  .note .meta{font-family:var(--mono);font-size:10.5px;color:var(--faint)}
  .note .body{margin-top:3px}
  form{margin-top:14px;display:grid;gap:9px}
  .target{font-family:var(--mono);font-size:11px;color:var(--muted)}
  select,textarea,input{background:var(--ink);color:var(--text);border:1px solid var(--line);
    border-radius:2px;padding:8px 9px;font-family:var(--mono);font-size:12px;width:100%}
  textarea{resize:vertical;min-height:64px;font-family:var(--sans)}
  .frow{display:flex;gap:9px}
  button{background:var(--verdigris);color:#0e1614;border:0;border-radius:2px;padding:9px 16px;
    font-family:var(--mono);font-size:12px;letter-spacing:.06em;text-transform:uppercase;
    cursor:pointer;font-weight:600}
  button:hover{filter:brightness(1.08)}
  :focus-visible{outline:2px solid var(--verdigris);outline-offset:2px}

  /* persona surface (view 5) removed with the persona profiler (D-GCW-6 / BT-4b) */
  .pgrid{display:grid;grid-template-columns:1fr 1fr;gap:26px;align-items:start;margin-bottom:22px}
  .ppanel{}
  .ptitle{font-family:var(--mono);font-size:11px;letter-spacing:.22em;text-transform:uppercase;
    color:var(--muted);margin:0 0 6px;display:flex;justify-content:space-between}
  .phelp{font-family:var(--display);font-style:italic;font-size:13px;color:var(--faint);
    margin:0 0 11px;line-height:1.35}
  .anchorrow{border:1px solid var(--line);border-left:2px solid var(--faint);background:var(--panel);
    padding:11px 13px;margin-bottom:9px}
  .anchorrow.divergent{border-left-color:var(--ochre)}
  .anchorrow .atop{display:flex;align-items:baseline;justify-content:space-between;gap:10px}
  .anchorrow .aname{font-family:var(--mono);font-size:12.5px;color:var(--verdigris)}
  .records{display:flex;gap:18px;margin-top:8px;font-family:var(--mono);font-size:11.5px;flex-wrap:wrap}
  .records .rec{color:var(--muted)} .records .rec b{color:var(--text);font-weight:600}
  .notice{margin-top:9px;font-family:var(--display);font-style:italic;font-size:13.5px;
    color:var(--ochre);line-height:1.35}
  .aff{display:flex;gap:6px;margin-top:9px}
  .aff .chip{cursor:default}
  /* queue badge */
  .queue-badge{display:flex;align-items:center}
  .queue-badge .chip{font-size:12px;padding:3px 10px;font-weight:600;letter-spacing:.05em}

  @media (max-width:900px){.grid{grid-template-columns:1fr}.vitals{grid-template-columns:repeat(3,1fr)}
    header{flex-direction:column;align-items:flex-start;gap:10px}.inscription{text-align:left}}
  @media (prefers-reduced-motion:reduce){*{transition:none!important}}
  .fade{animation:f .3s ease both}@keyframes f{from{opacity:0;transform:translateY(4px)}to{opacity:1}}
</style>
</head>
<body>
<div class="wrap">
  <header class="fade">
    <div class="brand">
      <h1>Genesis</h1><span class="eyebrow">QA&nbsp;console</span>
    </div>
    <div class="queue-badge" id="queueBadge"></div>
    <div class="inscription">γνῶθι σεαυτόν
      <span class="root" id="root">read-only · localhost · honest-empty</span>
    </div>
  </header>

  <div class="vitals fade" id="vitals"></div>

  <div class="grid">
    <div>
      <div class="colhead">Ledger — captured episodes <span class="count" id="cardCount"></span></div>
      <div id="cards"></div>
    </div>
    <div class="rail">
      <section>
        <div class="colhead">Security <span class="count" id="secCount"></span></div>
        <div id="security"></div>
      </section>
      <section>
        <div class="colhead">Infra <span class="count" id="infraCount"></span></div>
        <div id="infra"></div>
      </section>
      <section>
        <div class="colhead">QA notes</div>
        <div id="comments"></div>
        <form id="noteForm">
          <div class="target" id="noteTarget">Select an episode above to annotate it.</div>
          <div class="frow">
            <select id="section" aria-label="card section">
              <option value="ledger">ledger</option>
              <option value="gate">gate</option>
              <option value="security">security</option>
              <option value="infra">infra</option>
            </select>
            <select id="verdict" aria-label="verdict hint">
              <option value="">verdict…</option>
              <option value="correct">correct</option>
              <option value="over-flag">over-flag</option>
              <option value="missed">missed</option>
              <option value="wrong">wrong</option>
            </select>
          </div>
          <textarea id="comment" placeholder="What did the gate get right or wrong here?"></textarea>
          <button type="submit">File note</button>
        </form>
      </section>
    </div>
  </div>
  <!-- persona surface (view 5) removed with the persona profiler (D-GCW-6 / BT-4b) -->
</div>

<script>
const $ = s => document.querySelector(s);
let selected = null;

// action -> chip category (the gate's verdict language)
const CAT = {
  "gate-resolve":"ok","verdict":"ok","ask-resolved":"ok","day-processed":"ok","snapshot-verify":"ok",
  "gate-flag":"warn","ask-queued":"warn","drift-report":"warn","contest":"warn",
  "revert":"change","supersede":"change","class-migrate":"change","merge":"change",
  "worker-error":"alarm","lock-violation":"alarm","restore":"alarm",
  "scrub":"sec","redact":"sec","redact-cascade":"sec",
};
const cat = a => CAT[a] || "";
const esc = s => (s??"").toString().replace(/[&<>]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;"}[c]));
const shortTs = t => (t||"").replace("T"," ").replace(/(\\.\\d+)?(Z|[+-]\\d\\d:\\d\\d)?$/,"").slice(0,16);

function vitals(h){
  const v = [
    ["commits", h? h.commits:"—", ""],
    ["flag rate", h? (h.flag_rate*100).toFixed(0)+"%":"—", "key"],
    ["verdicts", h? h.verdicts:"—", ""],
    ["reverts", h? h.reverts:"—", ""],
    ["worker errors", h? h.worker_errors:"—", h&&h.worker_errors>0?"alarm":""],
  ];
  $("#vitals").innerHTML = v.map(([l,n,c]) =>
    `<div class="vital ${c}"><div class="n">${n}</div><div class="l">${l}</div></div>`).join("");
}

function cards(list){
  $("#cardCount").textContent = list.length ? list.length : "";
  if(!list.length){ $("#cards").innerHTML =
    `<div class="empty">No episodes captured yet. Capture fires on SessionEnd — end a session, then drain to extract.</div>`; return; }
  $("#cards").innerHTML = list.map(c => {
    const chips = [`<span class="chip ex-${esc(c.extracted)}">extracted: ${esc(c.extracted)}</span>`]
      .concat((c.actions||[]).map(a => `<span class="chip ${cat(a.action)}">${esc(a.action)}</span>`)).join("");
    const detail = (c.actions||[]).length ? (c.actions).map(a => `<div class="drow">
        <span class="chip ${cat(a.action)}">${esc(a.action)}</span>
        <span class="dk">${esc(a.target||a.scope||"")}</span>
        ${a.author?`<span class="da">${esc(a.author)}</span>`:""}
        <span class="rt">${shortTs(a.ts)}</span>
        ${a.reason?`<span class="dr">${esc(a.reason)}</span>`:""}</div>`).join("")
      : `<div class="dr" style="font-family:var(--display);font-style:italic;color:var(--faint)">Not drained yet — no supervision events. Run <code>genesis-worker once</code>.</div>`;
    return `<div class="card" data-eid="${esc(c.episode_id)}">
      <div class="top"><span class="eid">${esc(c.episode_id)}</span>
        <span class="ts">${shortTs(c.ts)}<span class="caret">▸</span></span></div>
      <div class="summary">${esc(c.summary)}</div>
      <div class="actions">${chips}</div>
      <div class="detail">${detail}</div></div>`;
  }).join("");
  document.querySelectorAll(".card").forEach(el => el.onclick = () => {
    el.classList.toggle("expanded");
    document.querySelectorAll(".card").forEach(x=>x.classList.remove("sel"));
    el.classList.add("sel"); selected = el.dataset.eid;
    $("#noteTarget").innerHTML = `Annotating <b style="color:var(--verdigris)">${esc(selected)}</b> — click a card to expand its detail`;
  });
}

function journalList(el, rows, emptyMsg){
  if(!rows.length){ el.innerHTML = `<div class="empty">${emptyMsg}</div>`; return; }
  el.innerHTML = rows.map(j => `<div class="row">
    <span class="chip ${cat(j.action)}">${esc(j.action)}</span>
    <span>${esc(j.target||j.scope||"")}</span>
    <span class="rt">${shortTs(j.ts)}</span></div>`).join("");
}

function comments(rows){
  $("#comments").innerHTML = rows.length ? rows.map(c => `<div class="note">
    <div class="meta">${esc(c.episode_id)} · ${esc(c.card_section)}${c.verdict_hint?" · "+esc(c.verdict_hint):""} · ${shortTs(c.ts)}</div>
    <div class="body">${esc(c.comment)}</div></div>`).join("")
    : `<div class="empty">No QA notes yet. Select an episode and file your read of the gate.</div>`;
}

// persona surface (view 5) removed with the persona profiler (D-GCW-6 / BT-4b)

async function load(){
  const m = await (await fetch("/api/model")).json();
  vitals(m.health); cards(m.cards||[]);
  const q = m.queue || {pending:0,in_progress:0,done:0};
  const qEl = $("#queueBadge");
  if(q.pending > 0){
    qEl.innerHTML = `<span class="chip warn">Queue: ${esc(q.pending)} pending</span>`;
  } else {
    qEl.innerHTML = `<span class="chip ok">Queue: 0 pending / all extracted</span>`;
  }
  journalList($("#security"), m.security||[], "Clean — no scrub or redaction events.");
  journalList($("#infra"), m.infra||[], "No worker errors or lock violations.");
  $("#secCount").textContent = (m.security||[]).length || "";
  $("#infraCount").textContent = (m.infra||[]).length || "";
  comments(await (await fetch("/api/comments")).json());
}

$("#noteForm").onsubmit = async e => {
  e.preventDefault();
  const comment = $("#comment").value.trim(); if(!comment) return;
  if(!selected){ $("#noteTarget").textContent = "Pick an episode first."; return; }
  await fetch("/api/comments", {method:"POST", headers:{"content-type":"application/json"},
    body: JSON.stringify({ ts:new Date().toISOString(), episode_id:selected,
      card_section:$("#section").value, comment, verdict_hint:$("#verdict").value||null })});
  $("#comment").value = ""; comments(await (await fetch("/api/comments")).json());
};

load();
</script>
</body>
</html>
"""
