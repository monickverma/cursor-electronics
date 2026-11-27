"""S2 bench-judge: drive Circuit OS as a black box and save every output.

Uses only the HTTP API at :8000 and kicad-cli on the files the product emits.
Usage: python -I run_product.py <out_dir> <prompt_file>
Writes generate.json, schematic.kicad_sch, bom.json, firmware.ino, explanation.json,
simulation.json, pcb_compile.json, board.svg, erc.json, timing.json into <out_dir>.
"""
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

BASE = os.environ.get("CIRCUIT_OS_URL", "http://127.0.0.1:8000")
KICAD = r"C:\Program Files\KiCad\10.0\bin\kicad-cli.exe"
TOKEN_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".token")


def call(method, path, body=None, token=None, timeout=180):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            status = r.status
    except urllib.error.HTTPError as e:
        raw, status = e.read(), e.code
    except Exception as e:  # timeout, refused
        return {"status": None, "error": repr(e), "seconds": round(time.time() - t0, 2)}
    try:
        payload = json.loads(raw)
    except ValueError:
        payload = raw.decode(errors="replace")
    return {"status": status, "body": payload, "seconds": round(time.time() - t0, 2)}


def token():
    if os.path.exists(TOKEN_FILE):
        t = open(TOKEN_FILE).read().strip()
        if call("GET", "/auth/me", token=t).get("status") == 200:
            return t
    email = f"s2judge{int(time.time())}@test.dev"
    r = call("POST", "/auth/register", {"email": email, "password": "TestPass123!"})
    t = r["body"]["access_token"]
    open(TOKEN_FILE, "w").write(t)
    return t


def save(out, name, obj):
    path = os.path.join(out, name)
    with open(path, "w", encoding="utf-8") as f:
        if isinstance(obj, str):
            f.write(obj)
        else:
            json.dump(obj, f, indent=1)
    return path


def main(out, prompt):
    os.makedirs(out, exist_ok=True)
    tok = token()
    timing = {}
    save(out, "prompt.txt", prompt)
    gpath = os.path.join(out, "generate.json")
    if os.path.exists(gpath):  # re-collect without spending a generate call
        g = json.load(open(gpath, encoding="utf-8"))
    else:
        g = call("POST", "/design/generate", {"prompt": prompt}, tok, timeout=300)
        save(out, "generate.json", g)
    timing["generate"] = {"status": g.get("status"), "seconds": g["seconds"]}
    body = g.get("body") if (g.get("status") or 0) // 100 == 2 else None
    if not isinstance(body, dict):
        save(out, "timing.json", timing)
        print(json.dumps({"generated": False, "status": g.get("status")}))
        return
    cid = body["circuit_id"]
    sch = save(out, "schematic.kicad_sch", body.get("schematic") or "")
    if body.get("firmware"):
        save(out, "firmware.ino", body["firmware"])
    for name, path in [("bom", f"/design/{cid}/bom"), ("firmware_view", f"/design/{cid}/firmware"),
                       ("explanation", f"/design/{cid}/explanation")]:
        r = call("GET", path, token=tok)
        timing[name] = {"status": r.get("status"), "seconds": r["seconds"]}
        save(out, f"{name}.json", r)
    sim = None
    if body.get("simulation_job_id"):
        for _ in range(20):
            sim = call("GET", f"/design/{cid}/simulation/{body['simulation_job_id']}", token=tok)
            st = (sim.get("body") or {}).get("status") if isinstance(sim.get("body"), dict) else None
            if st in ("complete", "failed", "error"):
                break
            time.sleep(3)
        save(out, "simulation.json", sim)
    if body.get("pcb_netlist"):
        p = call("POST", "/pcb/compile", body["pcb_netlist"], tok, timeout=300)
        timing["pcb_compile"] = {"status": p.get("status"), "seconds": p["seconds"]}
        save(out, "pcb_compile.json", p)
        if isinstance(p.get("body"), dict) and p["body"].get("svg"):
            save(out, "board.svg", p["body"]["svg"])
    erc = subprocess.run([KICAD, "sch", "erc", "--format", "json", "--severity-all",
                          "-o", os.path.join(out, "erc.json"), sch], capture_output=True, text=True)
    save(out, "erc_stdout.txt", erc.stdout + erc.stderr)
    save(out, "timing.json", timing)
    print(json.dumps({"generated": True, "circuit_id": cid, "timing": timing}))


if __name__ == "__main__":
    main(sys.argv[1], open(sys.argv[2], encoding="utf-8").read().strip())
