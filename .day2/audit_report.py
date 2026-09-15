"""Day 2 / Stage 9 — render npm audit JSON as a per-advisory table."""
import json
from pathlib import Path

d = json.loads((Path(__file__).with_name("npm_audit.json")).read_text(encoding="utf-8"))
print("=" * 78)
print("STAGE 9 — FRONTEND DEPENDENCY AUDIT (npm audit)")
print("=" * 78)
for name, v in d.get("vulnerabilities", {}).items():
    print(f"\n{name}  severity={v['severity']}  range={v.get('range')}  "
          f"direct={v.get('isDirect')}")
    fix = v.get("fixAvailable")
    if isinstance(fix, dict):
        print(f"  fix: {fix.get('name')}@{fix.get('version')}  "
              f"breaking={fix.get('isSemVerMajor')}")
    for via in v.get("via", []):
        if isinstance(via, dict):
            print(f"  - [{via.get('severity')}] {via.get('title')}")
            print(f"    {via.get('url')}")
            print(f"    cwe={via.get('cwe')}  cvss={via.get('cvss', {}).get('score')}")
        else:
            print(f"  - (transitively via {via})")
print("\ntotals:", json.dumps(d["metadata"]["vulnerabilities"]))
print("deps  :", json.dumps(d["metadata"]["dependencies"]))
