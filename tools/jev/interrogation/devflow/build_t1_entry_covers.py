"""T1 entry_covers_diff: labelled pairs built from real phase2-stage0 commits and their decisions.md entries.

Strata (label by construction):
  match          own entry                                                    -> covers
  mismatch_far   entry of another set commit with no shared non-test file     -> unrelated
  mismatch_near  entry of the set commit sharing the most non-test files      -> unrelated (lenient: or partial)
  partial        own entry with every unit naming one changed module removed  -> partially_covers_missing_named_item

Only 15 of the branch's 79 commits qualify (touch generators/proof/validation/IR/AI or their tests AND have an
identifiable decisions.md entry), so every commit contributes several constructed pairs. Author names and emails
are never read: git is called with --format= / %s only.
"""
import os
import re
from collections import OrderedDict

from common import SETS, git, redact, secret_findings, write_jsonl

DEC = ".claude/shared-memory/brain/decisions.md"

# (code commit, commit whose decisions.md holds its entry, heading prefixes or None=headings added there, pairing)
COMMITS = [
    ("c926fe6", "c926fe6", ["## [2026-08-07] Criterion 11 gate changed"], "entry_written_before_code(6eed3a6)"),
    ("cb211c4", "5bd3ad8", None, "entry_recorded_in_next_commit(5bd3ad8)"),
    ("2c53a3c", "2c53a3c", None, "same_commit"),
    ("3122e30", "3122e30", None, "same_commit"),
    ("d1ebbca", "d1ebbca", None, "same_commit"),
    ("26adf0b", "26adf0b", None, "same_commit"),
    ("dc94a08", "dc94a08", None, "same_commit"),
    ("9a4ecc6", "9a4ecc6", None, "same_commit"),
    ("60e68f7", "60e68f7", None, "same_commit"),
    ("0afa72c", "0afa72c", None, "same_commit"),
    ("1dee36a", "1dee36a", None, "same_commit"),
    ("dfba3ed", "dfba3ed", None, "same_commit"),
    ("69f2d66", "69f2d66", None, "same_commit"),
    ("bb3eb21", "bb3eb21", None, "same_commit"),
    ("1126d15", "1126d15", None, "same_commit"),
]
CODE_EXT = (".py", ".ts", ".tsx", ".j2", ".ini", ".yml", ".yaml", ".toml", ".cfg", ".txt")
MAX_DIFFSTAT = 60
MAX_SUMMARY_FILES = 45
MAX_NAMES = 10


def is_memory(path):
    return path.startswith(".claude/shared-memory/")


def is_test(path):
    return path.startswith("tests/") or "/tests/" in path or os.path.basename(path).startswith("test_") \
        or path.endswith(".spec.ts")



def stem(path):
    b = os.path.basename(path)
    for ext in (".ino.j2", ".spec.ts"):
        if b.endswith(ext):
            return b[: -len(ext)]
    return os.path.splitext(b)[0]


def split_entries(text):
    parts = re.split(r"(?m)^(?=## \[)", text)
    return [p.rstrip().rstrip("-").rstrip() for p in parts if p.startswith("## [")]


def entry_for(entry_commit, prefixes):
    text = git("show", f"{entry_commit}:{DEC}")
    entries = split_entries(text)
    if prefixes is None:
        diff = git("show", "--format=", entry_commit, "--", DEC)
        prefixes = [l[1:].strip() for l in diff.splitlines() if l.startswith("+## [")]
    chosen = [e for e in entries if any(e.startswith(p) for p in prefixes)]
    assert chosen, (entry_commit, prefixes)
    return "\n\n---\n\n".join(chosen), [e.splitlines()[0] for e in chosen]


_PY_DEF = re.compile(r"^\s*(?:async\s+)?def\s+([A-Za-z_]\w*)|^\s*class\s+([A-Za-z_]\w*)")
_TS_DEF = re.compile(r"^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s+([A-Za-z_]\w*)"
                     r"|^\s*(?:export\s+)?(?:const|let)\s+([A-Za-z_]\w*)\s*=\s*(?:async\s*)?\("
                     r"|^\s*(?:export\s+)?(?:interface|type)\s+([A-Za-z_]\w*)")
_VERSION = re.compile(r"""^\s*VERSION\s*=\s*["']([^"']+)["']""")
_HUNK = re.compile(r"^@@ [^@]+ @@\s*(.*)$")


def file_summary(sha, path):
    diff = git("show", "--format=", "--unified=0", sha, "--", path)
    added, removed, modified, v_old, v_new = [], [], [], None, None
    rx = _PY_DEF if path.endswith(".py") else _TS_DEF
    for line in diff.splitlines():
        m = _HUNK.match(line)
        if m and m.group(1):
            ctx = rx.match(m.group(1).strip()) if rx else None
            if ctx:
                name = next(g for g in ctx.groups() if g)
                if name not in modified:
                    modified.append(name)
            continue
        if line.startswith("+++") or line.startswith("---"):
            continue
        if line.startswith(("+", "-")):
            body = line[1:]
            vm = _VERSION.match(body)
            if vm:
                if line[0] == "+":
                    v_new = vm.group(1)
                else:
                    v_old = vm.group(1)
            m2 = rx.match(body) if rx else None
            if m2:
                name = next(g for g in m2.groups() if g)
                (added if line[0] == "+" else removed).append(name)
    both = [n for n in added if n in removed]
    out = OrderedDict()
    new = [n for n in dict.fromkeys(added) if n not in both]
    gone = [n for n in dict.fromkeys(removed) if n not in both]
    changed = list(dict.fromkeys(both + [n for n in modified if n not in new and n not in gone]))
    if new:
        out["added"] = new[:MAX_NAMES] + ([f"... +{len(new) - MAX_NAMES} more"] if len(new) > MAX_NAMES else [])
    if gone:
        out["removed"] = gone[:MAX_NAMES] + ([f"... +{len(gone) - MAX_NAMES} more"] if len(gone) > MAX_NAMES else [])
    if changed:
        out["changed"] = changed[:MAX_NAMES] + ([f"... +{len(changed) - MAX_NAMES} more"] if len(changed) > MAX_NAMES else [])
    if v_old or v_new:
        out["VERSION"] = f"{v_old or '(none)'} -> {v_new or '(removed)'}"
    return out


def commit_record(sha):
    subject = git("show", "-s", "--format=%s", sha).strip()
    rows = []
    for line in git("show", "--numstat", "--format=", sha).splitlines():
        if not line.strip():
            continue
        a, d, p = line.split("\t")
        if " => " in p:  # rename
            p = re.sub(r"\{[^}]*=> ([^}]*)\}", r"\1", p).replace("//", "/")
        rows.append((p, a, d))
    visible = [r for r in rows if not is_memory(r[0])]
    diffstat = [f"{p} | +{a} -{d}" for p, a, d in visible[:MAX_DIFFSTAT]]
    if len(visible) > MAX_DIFFSTAT:
        diffstat.append(f"... and {len(visible) - MAX_DIFFSTAT} more files")
    summary = OrderedDict()
    code_rows = [r for r in visible if r[0].endswith(CODE_EXT)]
    for p, a, d in code_rows[:MAX_SUMMARY_FILES]:
        s = file_summary(sha, p)
        if s:
            summary[p] = s
    if len(code_rows) > MAX_SUMMARY_FILES:
        summary["..."] = f"{len(code_rows) - MAX_SUMMARY_FILES} more code files not summarised"
    source = [(p, int(a) if a.isdigit() else 0) for p, a, d in visible
              if p.endswith(CODE_EXT) and not is_test(p) and p.startswith(("backend/", "frontend/", "scripts/"))]
    tests = [p for p, a, d in visible if is_test(p)]
    return {"sha": sha, "subject": subject, "diffstat": diffstat, "diff_summary": summary,
            "_source_files": source, "_test_files": tests}


# ------------------------------------------------------------------ partial construction
def units_of(entry):
    lines = entry.splitlines()
    head, body = lines[0], lines[1:]
    units, cur = [], []

    def flush():
        if cur:
            units.append("\n".join(cur))
            cur.clear()
    for line in body:
        if not line.strip():
            flush()
            units.append("")
            continue
        if re.match(r"^\s*(?:[-*]|\d+\.)\s+|^\s*\|", line) and cur:
            flush()
        cur.append(line)
    flush()
    return head, units


def mentions(text, aliases):
    low = text.lower()
    return any(re.search(r"(?<![a-z0-9_])" + re.escape(a.lower()) + r"(?![a-z0-9])", low) for a in aliases)


def aliases_for(path, summary):
    s = stem(path)
    al = {s}
    if "_" in s:
        al.add(s.replace("_", " "))
        al.add(s.replace("_", "-"))
    fs = summary.get(path, {})
    for n in fs.get("added", []):
        if n[0].isupper() and len(n) >= 8 and not n.startswith("..."):
            al.add(n)
    return sorted(al)


def trimmed(entry, aliases):
    head, units = units_of(entry)
    kept, removed = [], []
    for u in units:
        if u and mentions(u, aliases):
            removed.append(u)
        else:
            kept.append(u)
    text = head + "\n" + "\n".join(kept)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text, removed


# Topic words that still describe a module after its name is removed (fixed before any Jev call).
SYNONYMS = {
    "prover": ["proof", "prove"], "kicad": ["schematic"], "led_indicator": ["led"],
    "mcu_targets": ["target", "board"], "arduino": ["firmware", "arduino"], "intent_producer": ["producer"],
    "voltage_divider": ["divider"], "claims": ["claim"], "design": ["design"], "patch": ["patch"],
    "intent_patch": ["patch", "rfc 6902"], "explainer": ["explai"], "crud": ["crud"],
    "rc_lowpass": ["lowpass", "rc filter"], "envelope_grid": ["grid"], "registry": ["regist", "dispatch"],
    "form_producer": ["form"], "realize": ["realiz", "realis", "stamp"], "defeaters": ["defeater"],
    "pin_rules": ["pin"], "compile_gate": ["compile", "platformio"], "intent_ir": ["intentir", "intent ir"],
    "ir_schema": ["circuitir"], "protocol": ["protocol", "predict"], "derived_explainer": ["explai", "derived"],
    "spice": ["spice", "netlist"], "parser": ["parse"], "waveforms": ["waveform"],
}


def _norm(text):
    return re.sub(r"[-_ `*]", "", text.lower())


def topic_words(path):
    st = stem(path)
    toks = [t for t in re.split(r"[_.\-/]", st.lower()) if len(t) >= 4]
    words = [t[:6] for t in toks] + SYNONYMS.get(st, [])
    return sorted(set(words))


def residual(text, words):
    n = _norm(text)
    return sorted(w for w in words if _norm(w) in n)


def partials(rec, entry):
    head = entry.splitlines()[0]
    body_len = len(entry) - len(head)
    cands = []
    for path, added in sorted(rec["_source_files"], key=lambda x: -x[1]):
        al = aliases_for(path, rec["diff_summary"])
        if len(stem(path)) < 4 or not mentions(entry, al) or mentions(head, al):
            continue
        words = topic_words(path)
        text, removed = trimmed(entry, al)
        if not removed or mentions(text, al) or residual(text, words):
            continue
        if any(u.lstrip().startswith("## [") for u in removed):
            continue
        kept_ratio = (len(text) - len(head)) / max(body_len, 1)
        if kept_ratio < 0.35:
            continue
        cands.append({"kind": "module", "path": path, "added_lines": added, "aliases": al, "topic_words": words,
                      "text": text, "removed_units": [u[:120] for u in removed], "kept_ratio": round(kept_ratio, 3)})
    # VERSION bumps of existing generators are named items too (old -> new, new string not in the title)
    for path, fs in rec["diff_summary"].items():
        v = fs.get("VERSION", "") if isinstance(fs, dict) else ""
        m = re.match(r"^(\d+\.\d+\.\d+) -> (\d+\.\d+\.\d+)$", v)
        if not m:
            continue
        new = m.group(2)
        al = [new]
        if not mentions(entry, al) or mentions(head, al):
            continue
        text, removed = trimmed(entry, al)
        if not removed or mentions(text, al) or "version" in text.lower() and re.search(r"(?i)version (bump|change)", text):
            continue
        kept_ratio = (len(text) - len(head)) / max(body_len, 1)
        if kept_ratio < 0.35:
            continue
        cands.append({"kind": "version", "path": f"{path} VERSION {v}", "added_lines": 10**6, "aliases": al,
                      "topic_words": [], "text": text, "removed_units": [u[:120] for u in removed],
                      "kept_ratio": round(kept_ratio, 3)})
    cands.sort(key=lambda c: -c["added_lines"])
    out, seen = [], set()
    for c in cands:
        key = tuple(c["removed_units"])
        if key in seen:
            continue
        seen.add(key)
        out.append(c)
        if len(out) == 2:
            break
    return out


# ------------------------------------------------------------------ deterministic baseline
def det_baseline(rec, entry):
    src = [p for p, _ in rec["_source_files"] if len(stem(p)) >= 4]
    if not src:
        return {"label": "covers", "mention_fraction": None, "n_source_files": 0,
                "rule": "no non-test source files -> covers"}
    hit = [p for p in src if mentions(entry, aliases_for(p, rec["diff_summary"]))]
    f = len(hit) / len(src)
    lab = "covers" if f == 1.0 else ("partially_covers_missing_named_item" if f >= 0.25 else "unrelated")
    return {"label": lab, "mention_fraction": round(f, 3), "n_source_files": len(src),
            "rule": "fraction of changed non-test source files whose stem/alias the entry names: 1.0 covers, "
                    ">=0.25 partial, else unrelated"}


def build():
    recs, entries, titles = OrderedDict(), {}, {}
    for code_sha, entry_sha, prefixes, pairing in COMMITS:
        rec = commit_record(code_sha)
        rec["pairing"] = pairing
        recs[code_sha] = rec
        entries[code_sha], titles[code_sha] = entry_for(entry_sha, prefixes)
    order = list(recs)
    src_sets = {c: {p for p, _ in recs[c]["_source_files"]} | set(recs[c]["_test_files"]) for c in order}
    items = []
    far_use = {}

    def state(rec, entry):
        commit = {"subject": rec["subject"], "diffstat": rec["diffstat"], "diff_summary": rec["diff_summary"]}
        return {"commit": commit, "decision_entry": redact(entry)}

    for i, c in enumerate(order):
        rec = recs[c]
        own = entries[c]
        base = {"task": "T1", "commit": c, "commit_subject": rec["subject"], "pairing": rec["pairing"]}
        items.append({**base, "item_id": f"T1-{c}-match", "stratum": "match", "label": "covers",
                      "state": state(rec, own), "entry_from": c, "entry_titles": titles[c],
                      "label_rule": "the commit's own decisions.md entry",
                      "det_baseline": det_baseline(rec, own)})
        # far: no shared file; maximise distance in time order
        disjoint = [o for o in order if o != c and not (src_sets[o] & src_sets[c])]
        far = max(disjoint, key=lambda o: (-far_use.get(o, 0), abs(order.index(o) - i), -order.index(o))) \
            if disjoint else None
        if far:
            far_use[far] = far_use.get(far, 0) + 1
        if far:
            items.append({**base, "item_id": f"T1-{c}-far", "stratum": "mismatch_far", "label": "unrelated",
                          "state": state(rec, entries[far]), "entry_from": far, "entry_titles": titles[far],
                          "label_rule": "entry of another set commit sharing no changed file with this commit",
                          "det_baseline": det_baseline(rec, entries[far])})
        overlap = sorted(((len(src_sets[o] & src_sets[c]), -abs(order.index(o) - i), o)
                          for o in order if o != c), reverse=True)
        near = overlap[0][2] if overlap and overlap[0][0] > 0 else order[i - 1 if i > 0 else i + 1]
        near_rule = ("entry of the set commit sharing the most changed files "
                     f"({overlap[0][0]} shared)" if overlap and overlap[0][0] > 0
                     else "entry of the time-adjacent set commit (no commit shares a file)")
        if near == far:
            near = next(o for _, _, o in overlap[1:] if o != far)
        items.append({**base, "item_id": f"T1-{c}-near", "stratum": "mismatch_near", "label": "unrelated",
                      "lenient_labels": ["unrelated", "partially_covers_missing_named_item"],
                      "state": state(rec, entries[near]), "entry_from": near, "entry_titles": titles[near],
                      "label_rule": near_rule, "det_baseline": det_baseline(rec, entries[near])})
        for k, p in enumerate(partials(rec, own), 1):
            items.append({**base, "item_id": f"T1-{c}-partial{k}", "stratum": "partial",
                          "label": "partially_covers_missing_named_item", "state": state(rec, p["text"]),
                          "entry_from": c, "entry_titles": titles[c],
                          "omitted_item": {"kind": p["kind"], "path": p["path"], "aliases": p["aliases"],
                                           "topic_words_absent": p["topic_words"],
                                           "added_lines": p["added_lines"], "kept_ratio": p["kept_ratio"],
                                           "removed_units_prefix": p["removed_units"]},
                          "label_rule": "own entry with every paragraph/bullet naming one changed source module "
                                        "or VERSION bump removed (module/version not in the title; no path token "
                                        "or fixed synonym left anywhere); it still appears in diffstat and "
                                        "diff_summary",
                          "det_baseline": det_baseline(rec, p["text"])})
    for it in items:
        hits = secret_findings(it["state"])
        assert not hits, (it["item_id"], hits)
    return items


if __name__ == "__main__":
    items = build()
    h = write_jsonl(SETS / "t1_entry_covers.jsonl", items)
    from collections import Counter
    print(len(items), Counter(i["stratum"] for i in items), h)
