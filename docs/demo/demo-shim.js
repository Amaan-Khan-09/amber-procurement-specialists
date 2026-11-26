// Answers the page's /api/ requests from pre-computed files, so the page runs from any static host (GitHub Pages).
// Written next to index.html by amber/demo.py (the config below is filled in at build time).
(() => {
  "use strict";
  const CFG = {"files": {"leadtime-evidence": "files/leadtime_evidence.csv", "po-status": "files/po_status.csv", "26-32-13-engine-generators-alpha": "files/26_32_13_engine_generators_ALPHA.pdf", "kohler-2000reozmd-spec-sheet": "https://www.globalpwr.com/wp-content/uploads/cut-sheets/gps-kohler-2000-kw-reozmd-spec-sheet.pdf", "equipment-schedule": "files/equipment_schedule.csv", "multiquip-egc2000c-data-sheet": "https://service.multiquip.com/pdfs/EGC-2000C_Data_Sheet.pdf", "generac-md2000-spec-sheet": "https://generac.com/globalassets/products/business/stationary-generators/diesel-industrial-generators/spec-sheets/md2000-spec-sheet.pdf", "b1-northline-power": "files/B1_northline_power.pdf", "b2-tidewater-generator": "files/B2_tidewater_generator.pdf", "b3-keystone-energy": "files/B3_keystone_energy.pdf", "b4-ridgeway-power-email": "files/B4_ridgeway_power_email.txt", "cat-3516c-2000ekw-lehe1376": "https://emc.cat.com/n/api/pubdirect?media_string_id=LEHE1376-", "cummins-dqkab-submittal-csdg": "https://csdieselgenerators.com/Images/Generators/5104/new-cummins-dqkab-opu-submittal-csdg-5104-5105-1781896577.pdf", "kohler-kd2000-g5-626": "https://resources.kohler.com/power/kohler/industrial/pdf/g5626.pdf", "cummins-c2000d6e-spec-sheet": "https://csdieselgenerators.com/Images/Generators/4579/New-Cummins-C2000D6E-spec-sheet.pdf", "cummins-s-6786": "https://www.cummins.com/sites/default/files/2025-06/s-6786-spec-sheet.pdf", "kohler-2000rozd4-spec-sheet": "https://csdieselgenerators.com/Images/Generators/3592/Kohler-2000ROZD4-spec-sheet.pdf", "mtu-16v4000-ds2250-60hz-50c": "https://www.mtu-solutions.com/content/dam/mtu/products/power-generation/powergeneration-product-list-latest/231210_PG_Spec_16V4000DS2250G04_2250kW_3D_FC_60Hz_50C.pdf", "kohler-kd1000-submittal-wpc6593": "https://woodstockpower.com/wp-content/uploads/2024/09/WPC_PO-6593_1000-kW-KD1000_Submittal.pdf", "winnipeg-generator-shop-drawings": "https://legacy.winnipeg.ca/finance/findata/matmgt/documents/2016/803-2016/803-2016_Appendix_B_Generator_Shop_Drawings.pdf", "26-33-53-static-ups-alpha": "files/26_33_53_static_ups_ALPHA.pdf", "vertiv-exl-s1-package": "https://www.vertiv.com/4a5725/globalassets/products/critical-power/uninterruptible-power-supplies-ups/liebert-exl-s1-/liebert-exl-s1_300-to-1200-kw.pdf"}, "delivery": {"as_of": "2026-12-01", "result_id": "web:7dce16b88e304bbef184"}};
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
