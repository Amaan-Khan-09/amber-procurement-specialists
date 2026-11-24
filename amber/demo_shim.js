// Answers the page's /api/ requests from pre-computed files, so the page runs from any static host (GitHub Pages).
// Written next to index.html by amber/demo.py (the config below is filled in at build time).
(() => {
  "use strict";
  const CFG = __CONFIG__;
  const safe = rid => rid.replace(":", "__");
  window.__demoErrors = [];
  window.AMBER_DEMO = {
    reportUrl: rid => `reports/${safe(rid)}.html`,
    fileUrl: (doc, page) => { const u = CFG.files[doc]; return u ? (page && /\.pdf$/i.test(u) ? `${u}#page=${page}` : u) : null; },
  };
  const realFetch = window.fetch.bind(window);
  const reply = (obj, status = 200) => new Response(JSON.stringify(obj), {status, headers: {"Content-Type": "application/json"}});
  const cache = {};
  const get = p => cache[p] || (cache[p] = realFetch(p).then(r => { if (!r.ok) throw new Error(`${p}: ${r.status}`); return r.json(); }));
  const KEY = rid => "amber-demo-reviews:" + rid;
  const readReviews = rid => { try { return JSON.parse(localStorage.getItem(KEY(rid)) || "{}"); } catch { return {}; } };
  const writeReviews = (rid, v) => { try { localStorage.setItem(KEY(rid), JSON.stringify(v)); } catch { /* private mode: decisions last for this page view only */ } };
  const mem = {};  // fallback when localStorage is unavailable
  const NO_RUN = "This is a read-only demo of saved results. To run the agents on your own documents, install the project (see the README): no API key is needed to explore.";

  window.fetch = async (input, init = {}) => {
    const raw = typeof input === "string" ? input : input.url;
    const at = raw.indexOf("/api/");
    if (at < 0) return realFetch(input, init);
    const u = new URL(raw.slice(at), "http://demo.invalid"), path = u.pathname, method = (init.method || "GET").toUpperCase();
    try {
      if (path === "/api/state") return reply(await get("data/state.json"));
      if (path === "/api/overview") return reply(await get("data/overview.json"));
      if (path === "/api/proof") return reply(await get("data/proof.json"));
      const m = path.match(/^\/api\/results\/([^/]+)(?:\/(review|drafts))?$/);
      if (m) {
        const rid = decodeURIComponent(m[1]);
        const res = await get(`data/results/${safe(rid)}.json`);
        if (!m[2]) return reply({...res, reviews: mem[rid] || readReviews(rid)});
        if (m[2] === "drafts") return reply({drafts: res.result.result.follow_ups || []});
        const body = JSON.parse(init.body || "{}"), reviews = {...(mem[rid] || readReviews(rid))};
        if (!res.result.findings.some(f => f.id === body.finding)) return reply({error: "no such finding"}, 400);
        if (["", "clear", null, undefined].includes(body.decision)) delete reviews[body.finding];
        else if (["agree", "complies", "deviates", "missing", "unclear"].includes(body.decision)) reviews[body.finding] = {decision: body.decision, note: String(body.note || "").slice(0, 1000), at: new Date().toISOString().slice(0, 19)};
        else return reply({error: "decision must be agree, complies, deviates, missing or unclear"}, 400);
        mem[rid] = reviews; writeReviews(rid, reviews);
        return reply({reviews});
      }
      if (path === "/api/source") {
        const doc = u.searchParams.get("doc") || "", page = parseInt(u.searchParams.get("page") || "1", 10) || 1;
        const q = u.searchParams.get("q") || "", loc = u.searchParams.get("loc") || "";
        const [src, pages] = await Promise.all([get("data/sources.json"), get("data/pages.json")]);
        let e = src[`${doc}|${page}|${q}|${loc}`];
        if (!e && pages[doc]) {  // another page of one of our own PDFs (Prev / Next): the page without a highlight
          const n = pages[doc].pages, p = Math.min(Math.max(1, page), n);
          e = {kind: "pdf", name: pages[doc].name, pages: n, page: p, found: 0, scanned: false, top: null, rects: [], image: `data/pages/${doc}-${p}.jpg`};
        }
        return e ? reply({...e, doc_id: doc}) : reply({error: "that source is not part of the demo"}, 404);
      }
      if (path === "/api/run" && method === "POST") {
        const b = JSON.parse(init.body || "{}");
        if (b.tool === "assess_delivery_risk" && (b.args || {}).as_of === CFG.delivery.as_of) return reply({result_id: CFG.delivery.result_id, cached: false});
        return reply({error: b.tool === "assess_delivery_risk" ? `In the demo the forecast is available as of ${CFG.delivery.as_of}. ${NO_RUN}` : NO_RUN}, 400);
      }
      if (path === "/api/upload") return reply({error: NO_RUN}, 400);
      return reply({error: "not available in the demo"}, 404);
    } catch (e) {
      window.__demoErrors.push(`${path}: ${e.message}`);
      return reply({error: String(e.message)}, 500);
    }
  };
})();
