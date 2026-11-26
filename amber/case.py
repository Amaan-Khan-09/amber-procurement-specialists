"""run_case: one purchase, end to end, as a case file that remembers every step and resumes after an interruption.

Goal: "buy the four 2000 kW standby generators (GEN-A..D) for Project Alpha". The steps, in order:

  requirements  the spec's checkable requirements and the schedule's need date
  discover      who could supply it (vendor master + spec's manufacturer list + datasheet checks), ranked with evidence
  link          which records are about the same thing: bid -> datasheet (ambiguous links reported), bid form scope
                item -> spec paragraph, tags -> PO log -> lead-time evidence
  datasheets    each linked datasheet checked against the spec (saved model readings replayed; live for a new one)
  bids          the bid comparison (scope, leveled cost, lead times, terms)
  commitments   each bid read as the supplier's written commitment, against the same requirements
  reconcile     per requirement and per CONDITION, the strongest verified evidence across the supplier's documents;
                conflicts between records kept as conflicts; derating footnotes linked to the option they depend on
  prequalify    each bidder checked against the spec's and the owner's pre-qualification criteria
  ranges        leveled cost as a range (what is assumed, what is open-ended) and arrival dates P10/P50/P90 with
                their sources
  triage        every open item routed: decided / ask the supplier / an engineer must judge
  questions     one draft per supplier: every question cites what was read; never sent automatically
  replies       WAITS for supplier replies; each reply is read against that supplier's open items only, and what it
                settles (and what it costs) flows back into the answers, the pre-qualification and the leveled cost
  decision      the award stays with a person while blockers remain; the case file says which

The case file is a folder (runs/cases/<id>/): state.json (every step's status, input fingerprint and summary, plus the
memory the steps share), steps/<step>.json (each step's full output) and journal.jsonl (every event, append-only).
A step whose inputs have not changed is not run again, so an interrupted run resumes at the step it was in.
"""
from __future__ import annotations

import argparse
import copy
import glob
import hashlib
import json
import os
import re
import sys
import time
from datetime import date, datetime
from pathlib import Path

from . import __version__, checks, docs, evidence, linking, registries, submittal, triage, vendors
from .schema import Verdict
from .verify import verify

ROOT = Path(__file__).resolve().parents[1]
KEYS = ROOT / "eval" / "answer_keys"
EXAMPLES = ROOT / "examples"
CASES_DIR = Path(os.getenv("AMBER_CASES", ROOT / "runs" / "cases"))
AUTO = 0.70  # the hand-off line used everywhere

CASES = {
    "GEN": {
        "goal": "Buy the four 2000 kW standby generators (GEN-A..GEN-D) for Project Alpha, within budget, by the need date",
        "tag": "GEN-A", "tag_group": "GEN", "qty": 4, "class": "generator",
        "spec": "data/specs/project_alpha/26_32_13_engine_generators_ALPHA.pdf",
        "schedule": "data/schedules/equipment_schedule.csv", "po_status": "data/schedules/po_status.csv",
        "evidence": "data/leadtime_sources/leadtime_evidence.csv", "bid_form": "data/bids/00_bid_form_generators.pdf",
        "bids": {"B1": "data/bids/B1_northline_power.pdf", "B2": "data/bids/B2_tidewater_generator.pdf",
                 "B3": "data/bids/B3_keystone_energy.pdf", "B4": "data/bids/B4_ridgeway_power_email.txt"},
        "library": "data/submittals/*.pdf", "checklist": "eval/answer_keys/genset_requirements.json",
        "saved_package": "examples/package_GEN.json", "inbox": "data/replies", "as_of": "2026-11-26",
    },
}
STEPS = ["requirements", "discover", "link", "datasheets", "bids", "commitments", "reconcile", "prequalify", "ranges",
         "triage", "questions", "replies", "decision"]


class Interrupted(RuntimeError):
    """Raised on purpose (AMBER_CRASH_AT=<step>) to show that a run resumes where it stopped."""


class _NoModel:
    model = "none"


# ------------------------------------------------------------------ small helpers

def _sha(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()[:16]


def _file_sha(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()[:16]


def _code_sha() -> str:
    h = hashlib.sha256()
    for f in ("case.py", "triage.py", "linking.py", "vendors.py", "evidence.py", "inspect_evidence.py", "registries.py", "submittal.py", "checks.py", "verify.py", "bids.py"):
        h.update(Path(__file__).with_name(f).read_bytes().replace(b"\r\n", b"\n"))
    return h.hexdigest()[:12]


def _rel(p: str | Path) -> str:
    try:
        return Path(p).resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(p)


def saved_datasheet_runs() -> dict[str, dict]:
    """datasheet file name -> {"case": G7, "run": examples/G7.json}: the committed model readings of each datasheet."""
    out = {}
    for f in sorted(KEYS.glob("*.json")):
        if not re.fullmatch(r"[GU]\d+\.json", f.name):
            continue
        k = json.loads(f.read_text(encoding="utf-8"))
        run = EXAMPLES / f.name
        if run.exists():
            out[Path(k["submittal"]).name] = {"case": f.stem, "run": run}
    return out


def offers_from_run(run: dict) -> dict[str, dict]:
    """What the model reported for each condition, as kept in a saved check (the same as scripts/replay_decisions.py)."""
    offers: dict[str, dict] = {}
    for f in run["findings"]:
        for d in (f.get("data") or {}).get("conditions", []):
            o, cid = d.get("offered") or {}, d["cid"]
            if str(d.get("why", "")).startswith("not checked ("):
                offers[cid] = {"cid": cid, "not_checked": d["why"]}
                continue
            offers[cid] = {"cid": cid, "stated": bool(o.get("quote") or o.get("values")), "values": o.get("values") or [],
                           "unit": o.get("unit"), "selected": o.get("selected"), "quote": o.get("quote"),
                           "page": o.get("page"), "meets": o.get("meets")}
    return offers


def second_readings() -> dict[str, dict]:
    """datasheet case id -> {req_id: verdict} from the independent reader (eval/cross_checks/)."""
    f = ROOT / "eval" / "cross_checks" / "qwen3.8-27b.json"
    if not f.exists():
        return {}
    data = json.loads(f.read_text(encoding="utf-8"))
    return {cid: {rid: (a or {}).get("verdict") for rid, a in (v.get("answers") or {}).items()} for cid, v in data.items()}


def second_answers() -> dict[str, dict]:
    """datasheet case id -> {req_id: {"verdict", "quote", "page"}}: the independent reader's answers with its quotes."""
    f = ROOT / "eval" / "cross_checks" / "qwen3.8-27b.json"
    if not f.exists():
        return {}
    return {cid: dict(v.get("answers") or {}) for cid, v in json.loads(f.read_text(encoding="utf-8")).items()}


# ------------------------------------------------------------------ condition-level reconciliation

def _part(c: dict, offer: dict | None, doc: docs.Document) -> dict:
    d, cite, conf = submittal._decide_condition(c, offer, doc)
    return {"cid": c["cid"], "verdict": d.verdict.value, "why": d.why, "conf": round(conf, 3), "exact": d.exact,
            "cite": cite.model_dump(mode="json") if cite else None, "doc": doc.doc_id}


def _silent(p: dict) -> bool:
    return p["cite"] is None and p["verdict"] in ("missing", "unclear")


def merge_condition(dpart: dict, commits: list[dict]) -> dict:
    """dpart: the datasheet's decision for one condition. commits: the same condition decided on the supplier's own
    bid and replies, oldest first. Returns the reconciled decision with where it came from."""
    out = dict(dpart, source="datasheet", kind=None)
    for b in commits:
        if _silent(b):
            continue
        cur = out
        b_auto = b["conf"] >= AUTO
        if b["verdict"] == "deviates" and b_auto:
            out = dict(b, source=b["doc"], kind="commitment deviates",
                       why=f"the supplier's own document commits to something that does not meet it: {b['why']}")
        elif b["verdict"] == "complies" and b_auto:
            if cur["verdict"] == "complies":
                out = dict(b if b["conf"] >= cur["conf"] else cur, source=f"{cur['doc']} + {b['doc']}", kind="agree",
                           conf=max(b["conf"], cur["conf"]), why=f"{cur['why']} | confirmed by {b['doc']}: {b['why']}")
            elif cur["verdict"] == "deviates" and cur["conf"] >= AUTO and cur.get("source") == "datasheet":
                out = dict(cur, verdict="unclear", conf=0.5, source=f"{cur['doc']} vs {b['doc']}", kind="conflicting records",
                           why=f"conflicting records: {b['doc']} says {b['why']!r}, the datasheet shows {cur['why']!r}",
                           other_cite=b["cite"])
            else:
                out = dict(b, source=b["doc"], kind="committed in writing",
                           why=f"committed in {b['doc']}: {b['why']} (the datasheet: {cur['why'][:120]})")
        else:  # the supplier mentions it, but not as a firm, verifiable commitment
            if cur["verdict"] == "complies" and cur["conf"] >= AUTO:
                continue
            if cur["verdict"] == "deviates" and cur["conf"] >= AUTO and b["verdict"] in ("complies", "unclear"):
                out = dict(cur, verdict="unclear", conf=0.5, source=f"{cur['doc']} vs {b['doc']}", kind="conflicting records",
                           why=f"conflicting records: the datasheet shows {cur['why'][:120]!r}; {b['doc']} mentions "
                               f"{(b['cite'] or {}).get('quote', '')[:80]!r} ({b['why'][:100]})", other_cite=b["cite"])
            elif cur["verdict"] in ("missing", "unclear") or cur["conf"] < AUTO:
                if b["verdict"] == "complies" and cur["verdict"] in ("missing", "unclear"):
                    out = dict(b, source=b["doc"], kind="judged commitment",
                               why=f"{b['doc']}: {b['why']} (judged, not computed; the datasheet: {cur['why'][:100]})")
                elif cur["verdict"] in ("missing", "unclear"):
                    out = dict(cur, why=f"{cur['why']} | {b['doc']}: {b['why']}", other_cite=b["cite"],
                               kind=cur.get("kind") or ("partly stated" if b["cite"] else None))
    return out


def combine(parts: list[dict]) -> tuple[str, float, str]:
    vs = [p["verdict"] for p in parts]
    conf = min(p["conf"] for p in parts) if parts else 0.0
    why = "; ".join(p["why"] for p in parts)
    if "deviates" in vs:
        return "deviates", conf, why
    if "unclear" in vs:
        return "unclear", conf, why
    if all(v == "missing" for v in vs):
        return "missing", conf, why
    if "missing" in vs:
        return "unclear", min(conf, 0.6), "only partly stated: " + why
    return "complies", conf, why


# ------------------------------------------------------------------ related sections: conditional ratings

_FOOTNOTE = re.compile(r"(?is)([^.\n]{0,60}\b(?:enclos\w*|silencer\w*|sound\s+\w+|housing|canopy)[^.]{0,80}?\b(?:reduc\w*|derat\w*|lower\w*)"
                       r"[^.]{0,60}?ambient[^.]{0,60}?by\s*(\d+(?:\.\d+)?)\s*°?\s*C\s*\(\s*(\d+(?:\.\d+)?)\s*°?\s*F\s*\))")


def conditional_ratings(doc: docs.Document) -> list[dict]:
    """Footnotes that lower an ambient rating when an option is fitted ('Enclosure with enclosed silencer reduces
    ambient temperature capability by 5 C (9 F)'). Each is verified on its page."""
    out = []
    for p in doc.pages:
        src = re.sub(r"\s*\n\s*", " ", p.raw or p.text)
        for m in _FOOTNOTE.finditer(src):
            text = m.group(1).strip(" †*‡§")
            cite = verify(doc, text, p.number)
            if cite:
                out.append({"page": p.number, "text": text, "delta_c": float(m.group(2)), "delta_f": float(m.group(3)),
                            "citation": cite.model_dump(mode="json"),
                            "option_words": sorted(set(re.findall(r"(?i)enclos\w*|silencer\w*|sound|housing|canopy", text.lower())))})
    return out


_SILENCER_INSIDE = re.compile(r"(?i)silencers?\s+(?:mounted\s+)?inside|inside\s+silencers?|enclosed\s+silencers?|internal(?:-mounted)?\s*(?:,\s*)?(?:exhaust\s+)?silencers?")


def apply_conditional(reqs: list[dict], parts_by_req: dict[str, list[dict]], doc: docs.Document,
                      commitment_docs: list[docs.Document]) -> list[dict]:
    """If a footnote lowers an ambient rating when the silencer is enclosed, and the silencer IS enclosed (the
    supplier's own document says so, or the spec requires it), the lowered rating is the one to compare. The result is
    never automatic: interpreting a footnote is an engineer's call, so it is laid out with both quotes."""
    notes = conditional_ratings(doc)
    if not notes:
        return []
    spec_requires = next((r for r in reqs for c in r["conditions"] if "silencer" in str(c.get("attribute", ""))
                          and "inside" in [str(t).lower() for t in c.get("terms") or []]), None)
    applied = []
    for r in reqs:
        for i, c in enumerate(r["conditions"]):
            if c.get("kind", "numeric") != "numeric" or c.get("op") != ">=" or "ambient" not in str(c.get("attribute", "")):
                continue
            p = parts_by_req[r["req_id"]][i]
            vals = [v for v in re.findall(r"\d+(?:\.\d+)?", str((p.get("cite") or {}).get("quote", "")))]
            offered = None
            for v in vals:
                if c.get("unit") in ("°F", "F") and float(v) >= 100:
                    offered = float(v)
                    break
            note = notes[0]
            why_on, on_cite = None, None
            for cd in commitment_docs:
                for pg in cd.pages:
                    m = _SILENCER_INSIDE.search(pg.text)
                    if m:
                        cc = verify(cd, m.group(0), pg.number)
                        if cc:
                            why_on, on_cite = f"{cd.doc_id} commits to {m.group(0)!r}", cc.model_dump(mode="json")
                            break
                if why_on:
                    break
            if not why_on and spec_requires:
                why_on = f"the spec requires the silencer inside the enclosure ({spec_requires['req_id']}, {spec_requires.get('locator')})"
                on_cite = spec_requires.get("spec_citation")
            if not why_on:
                continue
            if offered is None:
                verdict, why = "unclear", (f"conditional rating: {note['text']!r} (p{note['page']}) applies because {why_on}; "
                                           "the base rating to reduce was not found in the evidence")
            else:
                lowered = offered - note["delta_f"]
                ok = lowered >= float(c["value"])
                verdict = "complies" if ok else "deviates"
                why = (f"conditional rating: {offered:g} °F less {note['delta_f']:g} °F per the footnote {note['text']!r} "
                       f"(p{note['page']}) = {lowered:g} °F, {'meets' if ok else 'below'} the required {c['value']} °F, "
                       f"because {why_on}")
            parts_by_req[r["req_id"]][i] = dict(p, verdict=verdict, why=why, conf=min(p["conf"], 0.6), kind="conditional rating",
                                                other_cite=note["citation"], third_cite=on_cite, source=p.get("source", "datasheet"))
            applied.append({"req_id": r["req_id"], "cid": c["cid"], "verdict": verdict, "why": why})
    return applied


CLARIFY = {"depends on an option", "one missing fact"}


def needs_person(verdict: str, conf: float, cites: list) -> bool:
    """The same rule as ToolResult.finalize: low confidence, unclear, or a claim with no verified source."""
    return conf < AUTO or verdict == "unclear" or (verdict != "missing" and not cites)


# ------------------------------------------------------------------ reconcile one supplier's package

def reconcile_supplier(reqs: list[dict], d_doc: docs.Document, d_offers: dict, c_docs: list[docs.Document],
                       c_offers: list[dict], second: dict | None = None, reader: dict | None = None,
                       inspect: bool = True, context: dict | None = None) -> dict:
    """Datasheet + the supplier's own documents (bid, replies) -> one finding per requirement, routed.
    reader: the independent reader's answers with quotes; inspect=False gives the version before the second look
    (amber/inspect_evidence.py), so both can be compared on the same readings."""
    d_offers = copy.deepcopy(d_offers)
    submittal._flag_shared_evidence(reqs, d_offers)
    c_offers = [copy.deepcopy(o) for o in c_offers]
    for o in c_offers:
        submittal._flag_shared_evidence(reqs, o)
    ds_meta = evidence.doc_meta(d_doc, "datasheet")
    metas = [evidence.doc_meta(cd, "reply" if "reply" in cd.doc_id else "bid") for cd in c_docs]
    parts_by_req, base_by_req, commit_by_req = {}, {}, {}
    for r in reqs:
        dparts = [_part(c, d_offers.get(c["cid"]), d_doc) for c in r["conditions"]]
        base_by_req[r["req_id"]] = dparts
        if inspect:
            from .inspect_evidence import compute_text, soften_absence
            for i, c in enumerate(r["conditions"]):
                d = dparts[i]
                got = compute_text(c, str((d.get("cite") or {}).get("quote", ""))) if d["verdict"] == "deviates" else None
                if got and got["verdict"] == "complies":  # the same words in another notation
                    dparts = dparts[:i] + [dict(d, verdict="complies", conf=0.8, why=got["why"])] + dparts[i + 1:]
                else:
                    dparts = dparts[:i] + [soften_absence(c, d)] + dparts[i + 1:]
        merged, kept = [], []
        for i, c in enumerate(r["conditions"]):
            commits = [_part(c, o.get(c["cid"]), cd) for cd, o in zip(c_docs, c_offers)]
            if inspect:  # a document that merely omits words does not contradict another that states them
                from .inspect_evidence import soften_absence
                commits = [soften_absence(c, p) for p in commits]
            res = evidence.resolve_commitments(commits, c_docs, metas) if inspect else \
                {"effective": list(range(len(commits))), "superseded": [], "conflict": None}
            m = merge_condition(dparts[i], [commits[j] for j in res["effective"]])
            if res["conflict"]:
                a, b = (commits[j] for j in res["conflict"])
                m = dict(a, verdict="unclear", conf=0.5, kind="conflicting records", source=f"{a['doc']} vs {b['doc']}",
                         other_cite=b["cite"], why=f"conflicting records from the supplier: {a['doc']} says {a['why'][:110]!r}; "
                                                   f"{b['doc']} says {b['why'][:110]!r}; neither says it replaces the other")
            merged.append(m)
            kept.append((commits, res))
        parts_by_req[r["req_id"]] = merged
        commit_by_req[r["req_id"]] = kept
    conditional = apply_conditional(reqs, parts_by_req, d_doc, c_docs)
    inspected = []
    if inspect:
        from .inspect_evidence import inspect_parts
        inspected = inspect_parts(reqs, parts_by_req, d_doc, reader)
    record = []
    for r in reqs:
        for i, c in enumerate(r["conditions"]):
            commits, res = commit_by_req[r["req_id"]][i]
            record += evidence.record_for(r, c, base_by_req[r["req_id"]][i], commits, res, parts_by_req[r["req_id"]][i],
                                          metas, ds_meta, context or {})
    findings = []
    for r in reqs:
        parts = parts_by_req[r["req_id"]]
        verdict, conf, why = combine(parts) if parts else ("unclear", 0.3, "no checkable condition")
        if not r.get("spec_citation"):
            conf = min(conf, 0.5)
        kinds = {p.get("kind") for p in parts}
        cites = [r["spec_citation"]] if r.get("spec_citation") else []
        for p in parts:
            for k in ("cite", "other_cite", "third_cite"):
                if p.get(k) and p[k] not in cites:
                    cites.append(p[k])
        f = {"id": f"F-{r['req_id']}", "claim": r.get("requirement", ""), "status": verdict, "confidence": round(conf, 3),
             "needs_human": needs_person(verdict, conf, cites), "why": why, "citations": cites,
             "data": {"req_id": r["req_id"], "locator": r.get("locator"), "sources": sorted({p.get("source", "datasheet") for p in parts}),
                      "conditions": [{"cid": p["cid"], "verdict": p["verdict"], "why": p["why"], "source": p.get("source"),
                                      "kind": p.get("kind")} for p in parts]}}
        if "conflicting records" in kinds:
            f["data"].update(route="ask_supplier", route_kind="conflicting records",
                             route_why="two records disagree; the supplier is asked to say which applies, with both quotes")
        elif kinds & CLARIFY and all(p.get("kind") in CLARIFY or (p["verdict"] == "complies" and p["conf"] >= AUTO)
                                     for p in parts):
            asks = [p for p in parts if p.get("kind") in CLARIFY]
            q = "; ".join(("is this option supplied: " + p["option"]["line"]) if p.get("option") else
                          ("please state: " + ", ".join(p.get("missing") or [])) for p in asks)
            f["data"].update(route="ask_supplier", route_kind="clarification", question=q,
                             route_why="one missing fact settles it, and the rest is met with verified evidence: " + q)
        elif "conditional rating" in kinds:
            f["data"].update(route="engineer", route_kind="conditional rating",
                             route_why="a footnote changes the rating when an option is fitted, and the option is fitted: an engineer confirms the lowered rating")
        rt = triage.route(f, (second or {}).get(r["req_id"]) if not any(p.get("source", "datasheet") != "datasheet" for p in parts) else
                          ((second or {}).get(r["req_id"]) if f["status"] in triage.OPEN else None))
        f["route"] = rt
        findings.append(f)
    return {"findings": findings, "conditional": conditional, "inspected": inspected, "evidence": record,
            "baseline": [{"req_id": r["req_id"], "parts": base_by_req[r["req_id"]]} for r in reqs]}


# ------------------------------------------------------------------ the case file

class CaseFile:
    def __init__(self, case_id: str, cfg: dict, root: Path | None = None, live: bool = False):
        self.id, self.cfg, self.live = case_id, cfg, live
        self.dir = (root or CASES_DIR) / case_id
        (self.dir / "steps").mkdir(parents=True, exist_ok=True)
        self.state_file = self.dir / "state.json"
        self.state = (json.loads(self.state_file.read_text(encoding="utf-8")) if self.state_file.exists() else
                      {"case": case_id, "goal": cfg["goal"], "created": datetime.now().isoformat(timespec="seconds"),
                       "version": __version__, "steps": {}, "memory": {}})

    # persistence
    def save(self) -> None:
        tmp = self.state_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.state, indent=1, default=str), encoding="utf-8")
        tmp.replace(self.state_file)  # atomic: a crash never leaves half a state file

    def log(self, event: str, **kw) -> None:
        with (self.dir / "journal.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"t": datetime.now().isoformat(timespec="seconds"), "event": event, **kw}, default=str) + "\n")

    def output(self, step: str) -> dict:
        return json.loads((self.dir / "steps" / f"{step}.json").read_text(encoding="utf-8"))

    @property
    def memory(self) -> dict:
        return self.state["memory"]

    def remember(self, key: str, value) -> None:
        self.memory[key] = value

    # inputs of each step: files it reads + outputs of the steps it depends on
    # what each step depends on: the files it reads, the outputs of earlier steps, and the memory it uses
    _MEMORY_USED = {"reconcile": ["replies_read"], "prequalify": ["replies_read"], "ranges": ["replies_read"],
                    "triage": ["replies_read"], "questions": ["replies_read"], "decision": ["replies_read"]}

    def _inputs(self, step: str) -> str:
        c = self.cfg
        files = {"requirements": [c["spec"], c["schedule"], c["checklist"]],
                 "discover": [str(vendors.DIRECTORY), str(registries.SNAPSHOT)], "link": [c["bid_form"], *c["bids"].values()],
                 "bids": [c["saved_package"]], "commitments": [*c["bids"].values()],
                 "prequalify": sorted(glob.glob(str(vendors.PACKETS / "*.pdf"))),
                 "replies": sorted(glob.glob(str(ROOT / c["inbox"] / "*"))) if self.memory.get("replies_allowed") else []}.get(step, [])
        if step == "replies":  # a reply is new information, not a consequence of earlier steps
            ups = {"asked": self.memory.get("asked_first")}
        else:
            ups = {s: self.state["steps"].get(s, {}).get("output_sha") for s in STEPS[:STEPS.index(step)] if s != "replies"}
        mem = {k: self.memory.get(k) for k in self._MEMORY_USED.get(step, [])}
        return _sha([step, _code_sha(), [(_rel(f), _file_sha(ROOT / f)) for f in files if (ROOT / f).exists()], ups, mem,
                     self.memory.get("replies_allowed", False) if step == "replies" else None])

    def run(self, until: str | None = None, crash_at: str | None = None) -> dict:
        crash_at = crash_at or os.getenv("AMBER_CRASH_AT")
        for n in range(3):  # a reply changes what earlier steps knew: they run again in the same call
            before = json.dumps(self.memory.get("replies_read"), sort_keys=True)
            stop = self._pass(until, crash_at if n == 0 else None)
            if stop or json.dumps(self.memory.get("replies_read"), sort_keys=True) == before:
                break
            self.log("replies changed the case", note="the steps that depend on the replies run again")
        return self.state

    def _pass(self, until: str | None, crash_at: str | None) -> bool:
        for step in STEPS:
            st = self.state["steps"].get(step, {})
            if st.get("status") == "running":
                self.log("interrupted", step=step, note="the previous run stopped inside this step; running it again")
                st["status"] = "interrupted"
            inputs = self._inputs(step)
            if st.get("status") in ("done", "waiting") and st.get("inputs") == inputs:
                self.log("reused", step=step)
                if step == until:
                    return True
                continue
            st.update(status="running", started=datetime.now().isoformat(timespec="seconds"), inputs=inputs,
                      attempts=st.get("attempts", 0) + 1)
            self.state["steps"][step] = st
            self.save()
            self.log("started", step=step, attempt=st["attempts"])
            t0 = time.time()
            out = getattr(self, f"step_{step}")(crash=(crash_at == step))
            (self.dir / "steps" / f"{step}.json").write_text(json.dumps(out, indent=1, default=str), encoding="utf-8")
            if out.get("_waiting"):
                st.update(status="waiting", summary=out["_waiting"], output_sha=_sha(out))
                self.save()
                self.log("waiting", step=step, why=out["_waiting"])
                continue  # later steps still run on what is known now; the case resumes when replies arrive
            st.update(status="done", finished=datetime.now().isoformat(timespec="seconds"), seconds=round(time.time() - t0, 2),
                      summary=out.get("_summary", ""), output_sha=_sha(out))
            self.save()
            self.log("done", step=step, summary=st["summary"])
            if step == until:
                return True
        return False

    # -------------------------------------------------------------- steps
    def _ck(self) -> list[dict]:
        return json.loads((ROOT / self.cfg["checklist"]).read_text(encoding="utf-8"))["requirements"]

    def _reqs(self) -> list[dict]:
        c = self.cfg
        spec = docs.load(ROOT / c["spec"])
        row = submittal.load_schedule(str(ROOT / c["schedule"]), c["tag"])
        return submittal.structure_requirements(_NoModel(), spec, row, docs.doc_id_for(ROOT / c["schedule"]), self._ck())

    def step_requirements(self, crash=False) -> dict:
        c = self.cfg
        row = submittal.load_schedule(str(ROOT / c["schedule"]), c["tag"])
        reqs = self._reqs()
        self.remember("need_date", row["need_on_site"])
        self.remember("as_of", c["as_of"])
        return {"_summary": f"{len(reqs)} requirements from spec {Path(c['spec']).name}; need on site {row['need_on_site']}",
                "tag": c["tag"], "need_on_site": row["need_on_site"], "schedule_row": row,
                "requirements": [{"req_id": r["req_id"], "locator": r.get("locator"), "requirement": r.get("requirement"),
                                  "conditions": len(r["conditions"]), "spec_citation": r.get("spec_citation")} for r in reqs]}

    def _datasheet_findings(self, path: str) -> tuple[list[dict], dict | None]:
        saved = saved_datasheet_runs().get(Path(path).name)
        if not saved:
            return [], None
        run = json.loads(saved["run"].read_text(encoding="utf-8"))
        return run["findings"], saved

    def step_discover(self, crash=False) -> dict:
        c = self.cfg
        lib = sorted(glob.glob(str(ROOT / c["library"])))
        saved = saved_datasheet_runs()
        reqs = self._reqs()
        fit: dict[str, dict] = {}
        by_file: dict[str, dict] = {}
        for p in lib:
            s = saved.get(Path(p).name)
            if not s:
                continue
            case = json.loads((KEYS / f"{s['case']}.json").read_text(encoding="utf-8"))
            if case["tag"] != c["tag"]:
                continue  # a datasheet checked for another size of set says nothing about this one
            d_doc = docs.load(p)
            offers = offers_from_run(json.loads(s["run"].read_text(encoding="utf-8")))
            submittal._flag_shared_evidence(reqs, offers)
            fs, _ = submittal.decide_all(reqs, offers, d_doc)
            scr = [f for f in fs if f.data["req_id"] in vendors.SCREEN]
            mfr = next((m for m in ("Caterpillar", "Cummins", "Kohler", "MTU") if m.lower() in d_doc.doc_id or m.lower() in Path(p).name.lower()
                        or (m == "Caterpillar" and "cat_" in Path(p).name)), None)
            entry = {"product": Path(p).name, "complies": sum(f.status == Verdict.complies for f in scr),
                     "deviates": sum(f.status == Verdict.deviates for f in scr),
                     "open": [f.data["req_id"] for f in scr if f.status.value in ("unclear", "missing")],
                     "quotes": [cc.model_dump(mode="json") for f in scr for cc in f.citations if cc.doc_id == d_doc.doc_id][:3]}
            if mfr and (mfr not in fit or entry["complies"] - 2 * entry["deviates"] > fit[mfr]["complies"] - 2 * fit[mfr]["deviates"]):
                fit[mfr] = entry
            by_file[Path(p).name] = entry
        pkg = json.loads((ROOT / c["saved_package"]).read_text(encoding="utf-8"))["result"]["parts"]["level_bids"]
        dirs = vendors.load_directory()
        bid_vendor = {r["bid_file"]: r["vendor_id"] for r in dirs if r["bid_file"]}
        offered = linking.link_products(pkg["products"], lib, pkg.get("product_citations"))
        for b, path in c["bids"].items():
            lk = offered[b]
            name = lk["datasheet"] or next((x["file"] for x in lk["candidates"] if x["kind"] == "variant"), None)
            if name in by_file and bid_vendor.get(Path(path).name):
                fit[bid_vendor[Path(path).name]] = dict(by_file[name], provisional=lk["status"] != "linked")
        by_file = bid_vendor
        bids = {}
        for b, path in c["bids"].items():
            vid = by_file.get(Path(path).name)
            lt = (pkg.get("lead_time") or {}).get(b) or {}
            if vid:
                bids[vid] = {"bid": b, "lead_max_weeks": lt.get("max_weeks"), "citation": lt.get("citation")}
        self.remember("bidder_vendor", {b: by_file.get(Path(p).name) for b, p in c["bids"].items()})
        row = submittal.load_schedule(str(ROOT / c["schedule"]), c["tag"])
        res = vendors.discover_vendors({"tag": c["tag"], "item": row["item"], "kw": float(row["standby_kw"]), "class": c["class"]},
                                       fit, bids, dirs)
        res["public_record"] = self._registry(bids_names=[r["name"] for r in dirs if r["bid_file"]])
        res["_summary"] = (f"{len((res['public_record'].get('discovery') or {}).get('candidates', []))} legal entities in federal "
                           f"award records for this size (looked up {res['public_record'].get('taken', '-')}); in the project's "
                           f"vendor master (mock) {len(res['ranked'])} vendors could supply it, {len(res['excluded'])} set aside; first: "
                           f"{res['ranked'][0]['name']} ({res['ranked'][0]['points']} points)")
        return res

    def _registry(self, bids_names: list[str] | None = None) -> dict:
        """Public registry lookups (amber/registries.py): live with --live, otherwise the saved, timestamped snapshot."""
        if self.live:
            try:
                return registries.refresh_snapshot(bids_names or [])
            except Exception as e:  # a lookup that fails is reported, never silently treated as clean
                self.log("registry refresh failed", why=str(e)[:200])
        return registries.snapshot() or {"taken": None, "discovery": {"status": "unavailable", "candidates": [],
                                         "why": "no saved lookup: run with --live"}, "screens": {}}

    def step_link(self, crash=False) -> dict:
        c = self.cfg
        pkg = json.loads((ROOT / c["saved_package"]).read_text(encoding="utf-8"))["result"]["parts"]["level_bids"]
        lib = sorted(glob.glob(str(ROOT / c["library"])))
        products = linking.link_products(pkg["products"], lib, pkg.get("product_citations"))
        form = docs.load(ROOT / c["bid_form"])
        scope = linking.link_scope_to_requirements(pkg["scope"], "\n".join(p.text for p in form.pages), self._ck())
        po = [r for r in _csv(ROOT / c["po_status"]) if r["tag_group"] == c["tag_group"]]
        sched = [r for r in _csv(ROOT / c["schedule"]) if r["tag"].startswith(c["tag_group"] + "-") and r["standby_kw"] == "2000"]
        records = {"tags": [r["tag"] for r in sched], "need_dates": sorted({r["need_on_site"] for r in sched}),
                   "po_log": po, "spec_section": sched[0]["spec_section"] if sched else None,
                   "why": f"{len(sched)} schedule rows with {c['tag_group']}- tags and 2000 kW; PO log group {c['tag_group']}: "
                          + (po[0]["status"] if po else "none")}
        self.remember("links", {b: {"status": v["status"], "datasheet": v["datasheet"]} for b, v in products.items()})
        self.remember("scope_links", {l["req_id"]: l["scope_id"] for l in scope["links"]})
        amb = [b for b, v in products.items() if v["status"] != "linked"]
        return {"_summary": f"{len(products) - len(amb)} of {len(products)} bids linked to a datasheet"
                            + (f"; ambiguous: {', '.join(amb)}" if amb else "")
                            + f"; {len(scope['links'])} scope items linked to spec requirements, {len(scope['conflicts'])} conflicting reference(s)",
                "products": products, "scope": scope, "records": records}

    def _datasheet_for(self, b: str) -> str | None:
        link = self.output("link")["products"][b]
        if link["datasheet"]:
            return link["datasheet"]
        # ambiguous: the closest candidate is checked provisionally, and every answer says so
        cands = [x for x in link["candidates"] if x["kind"] == "variant"] or link["candidates"]
        return cands[0]["file"] if cands else None

    def step_datasheets(self, crash=False) -> dict:
        out = {}
        for b in self.cfg["bids"]:
            name = self._datasheet_for(b)
            saved = saved_datasheet_runs().get(name or "")
            out[b] = {"datasheet": name, "saved_run": _rel(saved["run"]) if saved else None, "case": saved["case"] if saved else None,
                      "provisional": self.output("link")["products"][b]["status"] != "linked"}
            if not saved:
                out[b]["note"] = "no saved check of this datasheet: run check_submittal live"
        return {"_summary": "; ".join(f"{b}: {v['datasheet']} ({'provisional' if v['provisional'] else 'linked'})" for b, v in out.items()),
                **out}

    def step_bids(self, crash=False) -> dict:
        lb = json.loads((ROOT / self.cfg["saved_package"]).read_text(encoding="utf-8"))["result"]["parts"]["level_bids"]
        return {"_summary": f"{len(lb['matrix'])} bids compared on {len(lb['scope'])} scope items (saved readings)", **lb}

    def _commitment_offers(self, b: str, kind: str = "bid") -> tuple[list[docs.Document], list[dict]]:
        docs_, offers = [], []
        names = [f"{b}_bid"] + [Path(f).stem for f in self.memory.get("replies_read", {}).get(b, [])]
        for n in names:
            f = EXAMPLES / "commitments" / f"{n}.json"
            if not f.exists():
                continue
            run = json.loads(f.read_text(encoding="utf-8"))
            d = docs.load(ROOT / run["source_document"])
            d.commitment = True
            docs_.append(d)
            offers.append(offers_from_run(run))
        return docs_, offers

    def step_commitments(self, crash=False) -> dict:
        reqs = self._reqs()
        out = {}
        for b in self.cfg["bids"]:
            ds, os_ = self._commitment_offers(b)
            if not ds:
                out[b] = {"note": "the bid has not been read for its commitments: python scripts/read_commitments.py " + b}
                continue
            o = copy.deepcopy(os_[0])
            submittal._flag_shared_evidence(reqs, o)
            fs, _ = submittal.decide_all(reqs, o, ds[0])
            out[b] = {"doc": ds[0].doc_id, "stated": {f.data["req_id"]: {"status": f.status.value, "confidence": f.confidence,
                                                                         "why": f.why[:200]}
                                                      for f in fs if any(cc.doc_id == ds[0].doc_id for cc in f.citations)}}
        n = sum(len(v.get("stated", {})) for v in out.values())
        return {"_summary": f"{n} requirement answers found in the bids' own words (saved readings, decided again in code)", **out}

    def step_reconcile(self, crash=False) -> dict:
        reqs = self._reqs()
        seconds = second_readings()
        readers = second_answers()
        out, summary = {}, []
        for i, b in enumerate(self.cfg["bids"]):
            if crash and i == 2:
                raise Interrupted(f"stopped on purpose inside 'reconcile' after {i} of {len(self.cfg['bids'])} suppliers")
            name = self._datasheet_for(b)
            saved = saved_datasheet_runs().get(name or "")
            if not saved:
                out[b] = {"note": "no datasheet check"}
                continue
            d_doc = docs.load(ROOT / "data" / "submittals" / name)
            d_offers = offers_from_run(json.loads(saved["run"].read_text(encoding="utf-8")))
            c_docs, c_offers = self._commitment_offers(b)
            link = self.output("link")["products"][b]
            names = {r["vendor_id"]: r["name"] for r in vendors.load_directory()}
            context = {"supplier": names.get(self.memory["bidder_vendor"].get(b), b), "bid": b,
                       "tags": f"{self.cfg['tag_group']}-A..D", "model": link["product"],
                       "model_link": link["status"]}
            res = reconcile_supplier(reqs, d_doc, d_offers, c_docs, c_offers, seconds.get(saved["case"]), readers.get(saved["case"]),
                                     context=context)
            base = reconcile_supplier(reqs, d_doc, d_offers, [], [], seconds.get(saved["case"]), readers.get(saved["case"]))
            res["before_inspection"] = reconcile_supplier(reqs, d_doc, d_offers, c_docs, c_offers, seconds.get(saved["case"]),
                                                          inspect=False)["findings"]
            res["datasheet_only"] = base["findings"]
            res["datasheet_case"] = saved["case"]
            res["provisional"] = self.output("link")["products"][b]["status"] != "linked"
            out[b] = res
            changed = sum(1 for f, g in zip(res["findings"], base["findings"]) if (f["status"], f["route"]["route"]) != (g["status"], g["route"]["route"]))
            summary.append(f"{b}: {changed} answers changed by the supplier's own documents")
        return {"_summary": "; ".join(summary), **out}

    def step_prequalify(self, crash=False) -> dict:
        need = date.fromisoformat(self.memory["need_date"])
        as_of = date.fromisoformat(self.memory["as_of"])
        dirs = {r["vendor_id"]: r for r in vendors.load_directory()}
        bv = self.memory["bidder_vendor"]
        link = self.output("link")["products"]
        out = {}
        from .llm import LLM
        llm = LLM() if self.live else None
        for b, vid in bv.items():
            replies = [str(ROOT / json.loads((ROOT / f).read_text(encoding="utf-8"))["source_document"])
                       for f in self.memory.get("replies_read", {}).get(b, [])]
            documents = vendors.packet_for(vid) + replies
            hint = {"name": link[b]["product"], "citation": link[b].get("bid_citation")}
            out[b] = vendors.prequalify({"vendor_id": vid, "name": dirs[vid]["name"]}, documents, need, as_of, llm=llm,
                                        live=self.live, manufacturer_hint=hint, dir_row=dirs[vid])
            screen = (self.output("discover").get("public_record") or {}).get("screens", {}).get(dirs[vid]["name"])
            vendors.apply_registry(out[b], screen)
        return {"_summary": "; ".join(f"{b} {v['overall']}" for b, v in out.items()), **out}

    def step_ranges(self, crash=False) -> dict:
        lb = self.output("bids")
        pkg = json.loads((ROOT / self.cfg["saved_package"]).read_text(encoding="utf-8"))
        changes = self._price_changes()
        out = {}
        for b, lv in lb["leveling"].items():
            adj = dict(lv["adjustments"])
            to_confirm = dict(lv.get("to_confirm") or {})
            notes = list(lv.get("notes", []))
            for sid, ch in (changes.get(b) or {}).items():
                old = adj.get(sid)
                if ch["amount"] is None:
                    adj.pop(sid, None)
                    to_confirm.pop(sid, None)
                    notes.append(f"{sid}: confirmed included by the supplier's reply ({ch['source']}); allowance {old or 0:,.0f} removed")
                else:
                    adj[sid] = ch["amount"]
                    to_confirm.pop(sid, None)
                    notes.append(f"{sid}: priced by the supplier's reply at {ch['amount']:,.0f} ({ch['source']}), replacing {old or 0:,.0f}")
            high = lv["base"] + sum(adj.values())
            low = high - sum(to_confirm.values())
            open_ended = [{"risk": t.get("risk"), "note": t.get("note"), "citation": t.get("citation")}
                          for t in (lb.get("terms") or {}).get(b, []) if t.get("risk") in ("unquantified_cost", "short_validity", "escalation")]
            out[b] = {"base": lv["base"], "low": low, "high": high, "adjustments": adj, "to_confirm": to_confirm, "notes": notes,
                      "open_ended": open_ended,
                      "derivation": (f"base {lv['base']:,.0f} + allowances and alternates {sum(adj.values()):,.0f} = {high:,.0f} (high); "
                                     f"low = high minus {sum(to_confirm.values()):,.0f} for items read as 'qualified' that may turn out to "
                                     "be included" + ("; no upper bound for: " + "; ".join(o["note"] for o in open_ended if o["risk"] == "unquantified_cost")
                                                      if any(o["risk"] == "unquantified_cost" for o in open_ended) else ""))}
        dl = [f for f in pkg["findings"] if f["id"].startswith("delivery/")]
        arrivals = {}
        for f in dl:
            d = f["data"]
            if d.get("tag_group") != self.cfg["tag_group"]:
                continue
            arrivals[d["scenario"]] = {"P10": d["arrival"]["P10"], "P50": d["arrival"]["P50"], "P90": d["arrival"]["P90"],
                                       "p_late": d["p_late"], "lead_weeks": d.get("lead_weeks"),
                                       "submittal_weeks": d.get("submittal_weeks"), "evidence": d.get("evidence"),
                                       "need_on_site": d.get("need_on_site")}
        assumptions = ["2 weeks from award to purchase order (amber/delivery.py PROCURE_WEEKS)",
                       "a bid's lead time 'after approved submittals' adds the submittal cycle before the clock starts",
                       "market reports are weighted by who wrote them (contractor 1.0, vendor blog 0.6, trade press 0.5, recruiting 0.3); an outlier is kept as dissent and down-weighted",
                       "no production slot is reserved: a confirmed slot from the chosen supplier replaces the market range"]
        missing = ["Ridgeway (B4) gave 'approx 60 wks' with no basis (after order or after approval)",
                   "no supplier has confirmed a production slot"]
        return {"_summary": "cost ranges for " + ", ".join(f"{b} {v['low']:,.0f}-{v['high']:,.0f}" for b, v in out.items()),
                "cost": out, "arrival": arrivals, "assumptions": assumptions, "missing_inputs": missing}

    def step_triage(self, crash=False) -> dict:
        rec = self.output("reconcile")
        pq = self.output("prequalify")
        link = self.output("link")
        lb = self.output("bids")
        items = []
        for b in self.cfg["bids"]:
            for f in (rec.get(b) or {}).get("findings", []):
                items.append({"group": "requirement", "bid": b, "id": f["data"]["req_id"], "status": f["status"],
                              "confidence": f["confidence"], **f["route"], "claim": f["claim"]})
            for k, cr in (pq.get(b) or {}).get("criteria", {}).items():
                items.append({"group": "prequal", "bid": b, "id": k, "status": cr["status"], "route": cr["route"],
                              "kind": "owner check" if cr["route"] == "engineer" else cr["status"], "why": cr["why"], "claim": cr["text"]})
            lk = link["products"][b]
            items.append({"group": "link", "bid": b, "id": "product", "status": lk["status"], "route": lk["route"],
                          "kind": "product link", "why": lk["why"], "claim": lk["product"]})
        settled = self._price_changes()
        for f in json.loads((ROOT / self.cfg["saved_package"]).read_text(encoding="utf-8"))["findings"]:
            if f["id"].startswith("level_bids/F-B"):
                d = f["data"]
                ch = (settled.get(d["bid"]) or {}).get(d["scope_id"])
                if ch:  # the supplier's reply settled this scope item (via the requirement it is linked to)
                    items.append({"group": "bid scope", "bid": d["bid"], "id": d["scope_id"], "status": "included",
                                  "route": "decide", "kind": "settled by reply",
                                  "why": f"settled by {ch['source']} ({ch['req_id']}): {ch['quote'][:100]}", "claim": f["claim"]})
                    continue
                items.append({"group": "bid scope", "bid": d["bid"], "id": d["scope_id"], "status": d["scope_status"],
                              **triage.route_bid_cell(f), "claim": f["claim"]})
        items.append({"group": "decision", "bid": "-", "id": "award", "status": "escalate", "route": "engineer", "kind": "award",
                      "why": "an award is a person's decision; the case file lists what still blocks it", "claim": "award"})
        s = triage.summarize(items)
        by_group = {g: triage.summarize([i for i in items if i["group"] == g]) for g in sorted({i["group"] for i in items})}
        return {"_summary": f"{s['decide']} decided, {s['ask_supplier']} to the suppliers, {s['engineer']} to an engineer "
                            f"(of {s['total']})", "items": items, "summary": s, "by_group": by_group}

    def step_questions(self, crash=False) -> dict:
        tri = self.output("triage")
        rec = self.output("reconcile")
        drafts = {}
        for b in self.cfg["bids"]:
            qs = []
            fmap = {f["data"]["req_id"]: f for f in (rec.get(b) or {}).get("findings", [])}
            for it in tri["items"]:
                if it["bid"] == b and it["group"] == "requirement" and it["route"] == "decide" and it["status"] == "deviates":
                    f = fmap[it["id"]]
                    seen = [c for c in f["citations"][1:] if c.get("doc_id") and not str(c["doc_id"]).startswith("equipment")]
                    qs.append({"ref": it["id"], "ask": f"Spec {f['data']['locator']}: {f['claim']}. What you offer does not meet "
                                                       "it (quoted below): revise the offer or confirm the deviation",
                               "we_read": [{"doc": c["doc_id"], "page": c.get("page"), "quote": c.get("quote", "")[:140]} for c in seen[:2]],
                               "kind": "deviation: revise"})
                    continue
                if it["bid"] != b or it["route"] != "ask_supplier":
                    continue
                if it["group"] == "requirement":
                    f = fmap[it["id"]]
                    seen = [c for c in f["citations"][1:] if c.get("doc_id") and not str(c["doc_id"]).startswith("equipment")]
                    qs.append({"ref": it["id"], "ask": f"Spec {f['data']['locator']}: {f['claim']}. Please state what is supplied"
                                                       + (" and resolve the difference between your documents" if it.get("kind") == "conflicting records" else ""),
                               "we_read": [{"doc": c["doc_id"], "page": c.get("page"), "quote": c.get("quote", "")[:140]} for c in seen[:2]],
                               "kind": it.get("kind")})
                elif it["group"] == "prequal":
                    qs.append({"ref": it["id"], "ask": f"Pre-qualification {it['id']}: {it['claim']}. {it['why'][:160]}", "we_read": [],
                               "kind": "pre-qualification"})
                elif it["group"] == "link":
                    qs.append({"ref": "model", "ask": f"Confirm the exact model offered: {it['why'][:220]}", "we_read": [], "kind": "product link"})
                elif it["group"] == "bid scope":
                    qs.append({"ref": it["id"], "ask": f"Bid scope {it['id']}: {it['claim']}: {it['why'][:120]}", "we_read": [], "kind": "bid scope"})
            drafts[b] = {"to": self.memory["bidder_vendor"][b], "questions": qs, "status": "draft (never sent automatically)"}
        self.remember("asked", {b: [q["ref"] for q in d["questions"]] for b, d in drafts.items()})
        if "asked_first" not in self.memory:
            self.remember("asked_first", self.memory["asked"])
        return {"_summary": "; ".join(f"{b}: {len(d['questions'])} questions" for b, d in drafts.items()), "drafts": drafts}

    def _reply_owner(self, path: Path) -> str | None:
        head = path.read_text(encoding="utf-8", errors="ignore")[:400].lower() if path.suffix == ".txt" else \
            " ".join(p.text for p in docs.load(path).pages[:1])[:400].lower()
        dirs = {r["vendor_id"]: r["name"].lower() for r in vendors.load_directory()}
        for b, vid in self.memory["bidder_vendor"].items():
            if vid and dirs.get(vid) and dirs[vid].split(" (")[0] in head:
                return b
        return None

    def step_replies(self, crash=False) -> dict:
        inbox = ROOT / self.cfg["inbox"]
        files = sorted(p for p in inbox.glob("*") if p.is_file()) if self.memory.get("replies_allowed") else []
        if not files:
            return {"_waiting": f"waiting for supplier replies (questions drafted for {len(self.memory.get('asked', {}))} suppliers); "
                                "resume with --replies once they arrive", "read": []}
        read = []
        done = {b: list(v) for b, v in (self.memory.get("replies_read") or {}).items()}
        rec = self.output("reconcile")
        for p in files:
            b = self._reply_owner(p)
            if not b:
                read.append({"file": p.name, "note": "sender not matched to a bidder: a person files it"})
                continue
            name = f"{b}_reply"
            saved = EXAMPLES / "commitments" / f"{name}.json"
            # everything we sent back: open items, and deviations (a review comment asks the supplier to revise them)
            open_ids = [f["data"]["req_id"] for f in rec[b]["findings"]
                        if f["route"]["route"] != "decide" or f["status"] in ("missing", "deviates")]
            if not saved.exists():
                if not self.live:
                    read.append({"file": p.name, "bid": b, "note": "not read yet: run with --live (one model call per reply)"})
                    continue
                sys.path.insert(0, str(ROOT / "scripts"))
                import read_commitments  # noqa: E402
                read_commitments.read(p, name, only=open_ids)
            done[b] = sorted(set(done.get(b, [])) | {_rel(saved)})
            read.append({"file": p.name, "bid": b, "matched_by": "sender name in the vendor master", "asked": open_ids,
                         "saved_reading": _rel(saved)})
        self.remember("replies_read", done)
        self.log("replies read", files=[r["file"] for r in read])
        return {"_summary": f"{sum(1 for r in read if r.get('saved_reading'))} of {len(read)} replies read: "
                            + ", ".join(f"{r['bid']} ({len(r['asked'])} open items asked)" for r in read if r.get("saved_reading")),
                "read": read}

    def _line_of(self, cite: dict) -> str:
        """The whole line a verified quote sits on in a reply (a price is often in the same sentence, outside the quote)."""
        for f in self.memory.get("replies_read", {}).values():
            for saved in f:
                src = ROOT / json.loads((ROOT / saved).read_text(encoding="utf-8"))["source_document"]
                d = docs.load(src)
                if d.doc_id != cite.get("doc_id"):
                    continue
                pg = d.page(cite.get("page") or 1)
                q = re.sub(r"\s+", " ", cite.get("quote", "")).strip()[:40]
                for ln in (pg.text if pg else "").splitlines():
                    if q and q in re.sub(r"\s+", " ", ln):
                        return ln.strip()
        return cite.get("quote", "")

    def _price_changes(self) -> dict:
        """A reply that settles a requirement linked to a bid-form scope item changes that item's price: the supplier's
        own figure replaces the owner's allowance, or the allowance is removed when it is confirmed included."""
        out = {}
        if not self.memory.get("replies_read"):
            return out
        rec = self.output("reconcile")
        lb = self.output("bids")
        scope_links = self.memory.get("scope_links", {})
        for b in self.memory["replies_read"]:
            for f in rec[b]["findings"]:
                sid = scope_links.get(f["data"]["req_id"])
                reply_src = [s for s in f["data"]["sources"] if "reply" in s]
                if not sid or f["status"] != "complies" or not reply_src or lb["matrix"][b].get(sid) == "included":
                    continue
                qtxt = " ".join(self._line_of(c) for c in f["citations"] if "reply" in str(c.get("doc_id", "")))
                m = re.search(r"\$\s?([\d,]+)\s*(per set|each|/set)?", qtxt)
                amount = float(m.group(1).replace(",", "")) * (self.cfg["qty"] if m and m.group(2) else 1) if m else None
                out.setdefault(b, {})[sid] = {"amount": amount, "source": reply_src[0], "req_id": f["data"]["req_id"],
                                              "quote": qtxt[:160], "was": lb["matrix"][b].get(sid)}
        return out

    def step_decision(self, crash=False) -> dict:
        rg = self.output("ranges")
        pq = self.output("prequalify")
        rec = self.output("reconcile")
        link = self.output("link")["products"]
        tri = self.output("triage")
        rows = []
        for b in self.cfg["bids"]:
            fs = (rec.get(b) or {}).get("findings", [])
            dev = [f["data"]["req_id"] for f in fs if f["status"] == "deviates"]
            blockers = []
            if dev:
                blockers.append(f"{len(dev)} requirement(s) not met: {', '.join(dev)}")
            if pq[b]["overall"] == "fails":
                blockers.append(f"pre-qualification fails: {', '.join(pq[b]['fails'])}")
            elif pq[b]["to_verify"]:
                blockers.append(f"pre-qualification to verify: {', '.join(pq[b]['to_verify'])}")
            if link[b]["status"] != "linked":
                blockers.append("the exact product is not confirmed")
            n_eng = sum(1 for i in tri["items"] if i["bid"] == b and i["route"] == "engineer")
            n_sup = sum(1 for i in tri["items"] if i["bid"] == b and i["route"] == "ask_supplier")
            hard = len(blockers)
            if n_sup:
                blockers.append(f"{n_sup} question(s) open with the supplier")
            if n_eng:
                blockers.append(f"{n_eng} item(s) for an engineer")
            if pq[b].get("owner_checks"):
                blockers.append(f"owner's checks: {', '.join(pq[b]['owner_checks'])} (federal exclusion list)")
            arr = rg["arrival"].get(f"award to {b}") or {}
            rows.append({"bid": b, "vendor": self.memory["bidder_vendor"][b], "cost_low": rg["cost"][b]["low"],
                         "cost_high": rg["cost"][b]["high"], "arrival_P50": arr.get("P50"), "arrival_P90": arr.get("P90"),
                         "p_late": arr.get("p_late"), "prequal": pq[b]["overall"], "blockers": blockers,
                         "open_with_supplier": n_sup, "open_with_engineer": n_eng, "hard_blockers": hard})
        rows.sort(key=lambda r: (r["hard_blockers"], r["open_with_supplier"] + r["open_with_engineer"], r["cost_high"]))
        late = all((r["p_late"] or 0) >= 0.5 for r in rows if r["p_late"] is not None)
        return {"_summary": "a person decides: " + ("every option is likely late; " if late else "")
                            + f"closest to an award: {rows[0]['bid']} ({'; '.join(rows[0]['blockers']) or 'nothing open'})",
                "options": rows, "auto_award": False, "escalate_schedule": late,
                "why": "the award is never automatic here: it weighs cost ranges, open supplier questions, pre-qualification "
                       "and a schedule every option is likely to miss"}


def _csv(path: Path) -> list[dict]:
    import csv
    with open(path, encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def run_case(case_id: str = "GEN", until: str | None = None, replies: bool = False, live: bool = False,
             crash_at: str | None = None, root: Path | None = None, fresh: bool = False) -> CaseFile:
    cf = CaseFile(case_id, CASES[case_id], root=root, live=live)
    if fresh:
        import shutil
        shutil.rmtree(cf.dir, ignore_errors=True)
        cf = CaseFile(case_id, CASES[case_id], root=root, live=live)
    if replies and not cf.memory.get("replies_allowed"):
        cf.remember("replies_allowed", True)
        cf.log("replies released", note="supplier replies may now be read from the inbox")
        cf.save()
    cf.run(until=until, crash_at=crash_at)
    return cf


def main() -> None:
    ap = argparse.ArgumentParser(description="Run, resume or inspect a purchase case file.")
    ap.add_argument("command", choices=["run", "status"])
    ap.add_argument("--case", default="GEN")
    ap.add_argument("--until", help="stop after this step")
    ap.add_argument("--crash-at", help="stop on purpose inside this step (to show resuming)")
    ap.add_argument("--replies", action="store_true", help="read supplier replies from the inbox")
    ap.add_argument("--live", action="store_true", help="allow model calls for documents with no saved reading")
    ap.add_argument("--fresh", action="store_true", help="start the case file again from nothing")
    a = ap.parse_args()
    if a.command == "run":
        try:
            cf = run_case(a.case, a.until, a.replies, a.live, a.crash_at, fresh=a.fresh)
        except Interrupted as e:
            print(f"INTERRUPTED: {e}. Run the same command again (without --crash-at) to resume.")
            return
    else:
        cf = CaseFile(a.case, CASES[a.case])
    for s in STEPS:
        st = cf.state["steps"].get(s, {})
        print(f"{s:13} {st.get('status', '-'):12} {str(st.get('attempts', '')):>2}  {st.get('summary', '')[:110]}")


if __name__ == "__main__":
    main()


# ------------------------------------------------------------------ as MCP tool results (amber/server.py)

_PQ = {"meets": "complies", "fails": "deviates", "needs_verification": "unclear"}


def _cites(cs: list) -> list:
    from .schema import Citation
    out = []
    for c in cs or []:
        if c and c.get("doc_id") and c.get("quote"):
            out.append(Citation(doc_id=c["doc_id"], page=max(1, int(c.get("page") or 1)), locator=c.get("locator") or "",
                                quote=c["quote"], match=c.get("match") or "exact", ocr=bool(c.get("ocr"))))
    return out


def as_tool_result(cf: CaseFile, part: str):
    """part: 'case' (everything), 'discover' or 'prequalify'."""
    from .schema import Finding, RunInfo, ToolResult
    fs = []
    if part in ("case", "discover"):
        d = cf.output("discover")
        for v in d["ranked"]:
            fs.append(Finding(id=f"F-vendor-{v['vendor_id']}", claim=f"#{v['rank']} {v['name']} ({', '.join(v['manufacturers'])}): {v['points']} points",
                              status="unclear" if v["needs_engineer"] else "complies", confidence=0.6 if v["needs_engineer"] else 0.8,
                              needs_human=v["needs_engineer"], citations=_cites(v["citations"]), why="; ".join(v["reasons"]),
                              data={"vendor_id": v["vendor_id"], "rank": v["rank"], "points": v["points"], "product": v["product"]}))
        for x in d["excluded"]:
            fs.append(Finding(id=f"F-vendor-{x['vendor_id']}", claim=f"set aside: {x['name']}", status="deviates", confidence=0.9,
                              citations=_cites(x["citations"]), why=x["why"], data={"vendor_id": x["vendor_id"], "excluded": True}))
    if part in ("case", "prequalify"):
        for b, v in cf.output("prequalify").items():
            if b.startswith("_"):
                continue
            for k, c in v["criteria"].items():
                fs.append(Finding(id=f"F-prequal-{b}-{k}", claim=f"{v['name']} {k}: {c['text']}", status=_PQ[c["status"]],
                                  confidence=0.9 if c["status"] != "needs_verification" else 0.5, needs_human=c["route"] == "engineer",
                                  citations=_cites(c["citations"]), why=c["why"],
                                  data={"bid": b, "criterion": k, "status": c["status"], "route": c["route"]}))
    if part == "case":
        for b, v in cf.output("reconcile").items():
            if b.startswith("_") or "findings" not in v:
                continue
            for f in v["findings"]:
                fs.append(Finding(id=f"F-{b}-{f['data']['req_id']}", claim=f"{b}: {f['claim']}", status=f["status"],
                                  confidence=f["confidence"], needs_human=f["route"]["route"] == "engineer",
                                  citations=_cites(f["citations"]), why=f["why"][:600],
                                  data={"bid": b, **f["data"], "route": f["route"]}))
    res = ToolResult(tool={"case": "run_case", "discover": "discover_vendors", "prequalify": "prequalify_vendors"}[part], findings=fs,
                     result={"case": cf.id, "goal": cf.state["goal"],
                             "steps": {s: {k: v.get(k) for k in ("status", "attempts", "summary")} for s, v in cf.state["steps"].items()},
                             **({"decision": cf.output("decision"), "triage": cf.output("triage")["summary"],
                                 "questions": cf.output("questions")["drafts"]} if part == "case" else {}),
                             "case_folder": _rel(cf.dir)},
                     run=RunInfo())
    return res.finalize()
