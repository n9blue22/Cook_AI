"""Tóm tắt log JSONL của perf_server.py: thời gian phía server (min / trung vị / max) theo endpoint + trung vị từng
giai đoạn. Chạy: venv\\Scripts\\python.exe scripts/perf/perf_summary.py <đường dẫn log>"""

import json
import statistics
import sys
from collections import defaultdict


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    rows = [json.loads(line) for line in open(sys.argv[1], encoding="utf-8")]
    requests = defaultdict(list)
    for row in rows:
        if "path" in row and row["status"] < 400:
            requests[f'{row["method"]} {row["path"]}'].append(row)
    for endpoint, items in requests.items():
        totals = [item["total_ms"] for item in items]
        print(f"{endpoint}: n={len(totals)} min={min(totals):.0f} trung vị={statistics.median(totals):.0f} "
              f"max={max(totals):.0f} ms")
        stages = defaultdict(list)
        for item in items:
            for name, ms, _start in item["stages"]:
                stages[name].append(ms)
        for name, values in stages.items():
            print(f"    {name}: trung vị {statistics.median(values):.0f} ms")
    lags = [row["loop_lag_ms"] for row in rows if "loop_lag_ms" in row]
    print(f"event loop nghẽn >30 ms: {len(lags)} lần" + (f", lớn nhất {max(lags):.0f} ms" if lags else ""))


if __name__ == "__main__":
    main()
