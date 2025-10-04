# api/latency.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any
import json
import math
import os

app = FastAPI()

# Allow CORS for POST from any origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST"],
    allow_headers=["*"],
)

class Query(BaseModel):
    regions: List[str]
    threshold_ms: float

def load_telemetry(path="data/telemetry.json"):
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def percentile_95(values: List[float]) -> float:
    if not values:
        return 0.0
    vals = sorted(values)
    k = (len(vals) - 1) * 0.95
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return vals[int(k)]
    return vals[f] * (c - k) + vals[c] * (k - f)

@app.post("/api/latency")
async def latency_check(q: Query):
    try:
        data = load_telemetry()
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="telemetry file not found on server (data/telemetry.json)")

    out: Dict[str, Dict[str, Any]] = {}
    for region in q.regions:
        region_records = [r for r in data if r.get("region") == region]
        if not region_records:
            out[region] = {
                "avg_latency": None,
                "p95_latency": None,
                "avg_uptime": None,
                "breaches": 0,
            }
            continue

        latencies = [float(r.get("latency_ms", 0)) for r in region_records]
        uptimes = [float(r.get("uptime_pct", 0)) for r in region_records]

        avg_latency = sum(latencies) / len(latencies)
        p95_latency = percentile_95(latencies)
        avg_uptime = sum(uptimes) / len(uptimes)
        breaches = sum(1 for v in latencies if v > q.threshold_ms)

        out[region] = {
            "avg_latency": round(avg_latency, 3),
            "p95_latency": round(p95_latency, 3),
            "avg_uptime": round(avg_uptime, 3),
            "breaches": int(breaches),
        }

    return {"results": out}
