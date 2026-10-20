"""Concurrency, throughput, and memory profiling stress tests for ClauseGuard."""
from __future__ import annotations

import gc
import logging
import resource
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend"))
sys.path.insert(0, str(REPO_ROOT / "ml" / "src"))

from app.main import app

logger = logging.getLogger("stress_concurrency")


def _get_rss_mb() -> float:
    """Return process resident set size in megabytes."""
    rusage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    # On macOS, ru_maxrss is in bytes; on Linux, in kilobytes
    if sys.platform == "darwin":
        return round(rusage / (1024.0 * 1024.0), 2)
    return round(rusage / 1024.0, 2)


def _calc_latency_stats(latencies: List[float]) -> Dict[str, float]:
    """Calculate latency statistics percentiles."""
    if not latencies:
        return {}
    arr = np.array(latencies)
    return {
        "min_sec": round(float(np.min(arr)), 4),
        "mean_sec": round(float(np.mean(arr)), 4),
        "p50_sec": round(float(np.percentile(arr, 50)), 4),
        "p90_sec": round(float(np.percentile(arr, 90)), 4),
        "p95_sec": round(float(np.percentile(arr, 95)), 4),
        "max_sec": round(float(np.max(arr)), 4),
    }


def run_concurrency_stress_tests(max_workers: int = 5) -> Dict[str, Any]:
    """Run concurrent analysis, redline, search and memory profiling."""
    results: Dict[str, Any] = {}
    doc01_path = REPO_ROOT / "clauseguard-testkit" / "contracts" / "DOC-01_freelance_agreement.txt"
    doc01_bytes = doc01_path.read_bytes()

    with TestClient(app) as client:
        # Pre-seed one document for search testing
        init_resp = client.post(
            "/api/v1/analyze",
            files={"file": ("seed_doc01.txt", doc01_bytes, "text/plain")},
        )
        assert init_resp.status_code == 200, f"Seed failed: {init_resp.text}"
        seed_doc_id = init_resp.json()["document_id"]

        # 1. Concurrent Analysis Load Test
        t_start = time.time()
        latencies_analyze: List[float] = []
        statuses_analyze: List[int] = []

        def worker_analyze(i: int) -> tuple[int, float]:
            worker_client = TestClient(app)
            t0 = time.time()
            resp = worker_client.post(
                "/api/v1/analyze",
                files={"file": (f"stress_load_{i}.txt", doc01_bytes, "text/plain")},
            )
            return resp.status_code, time.time() - t0

        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = [pool.submit(worker_analyze, i) for i in range(max_workers)]
            for f in futures:
                code, dur = f.result()
                statuses_analyze.append(code)
                latencies_analyze.append(dur)

        total_time_analyze = time.time() - t_start
        success_analyze = sum(1 for s in statuses_analyze if s == 200)

        results["concurrent_analyze"] = {
            "workers": max_workers,
            "total_requests": len(statuses_analyze),
            "successful_requests": success_analyze,
            "success_rate_pct": round((success_analyze / len(statuses_analyze)) * 100, 2),
            "total_elapsed_sec": round(total_time_analyze, 3),
            "throughput_rps": round(len(statuses_analyze) / total_time_analyze, 2),
            "latency": _calc_latency_stats(latencies_analyze),
        }

        # 2. Concurrent Redline Load Test (30 requests)
        t_start = time.time()
        latencies_redline: List[float] = []
        statuses_redline: List[int] = []

        def worker_redline(i: int) -> tuple[int, float]:
            worker_client = TestClient(app)
            payload = {
                "clause_label": "Termination for Convenience",
                "clause_text": f"Client may terminate this Agreement at any time for no reason by giving Contractor 24 hours written notice (iter {i}).",
            }
            t0 = time.time()
            resp = worker_client.post("/api/v1/redline", json=payload)
            return resp.status_code, time.time() - t0

        redline_req_count = 30
        with ThreadPoolExecutor(max_workers=10) as pool:
            futures = [pool.submit(worker_redline, i) for i in range(redline_req_count)]
            for f in futures:
                code, dur = f.result()
                statuses_redline.append(code)
                latencies_redline.append(dur)

        total_time_redline = time.time() - t_start
        success_redline = sum(1 for s in statuses_redline if s == 200)

        results["concurrent_redline"] = {
            "total_requests": len(statuses_redline),
            "successful_requests": success_redline,
            "success_rate_pct": round((success_redline / len(statuses_redline)) * 100, 2),
            "total_elapsed_sec": round(total_time_redline, 3),
            "throughput_rps": round(len(statuses_redline) / total_time_redline, 2),
            "latency": _calc_latency_stats(latencies_redline),
        }

        # 3. Concurrent Search Load Test (30 requests)
        t_start = time.time()
        latencies_search: List[float] = []
        statuses_search: List[int] = []
        search_queries = [
            "when can I terminate?",
            "what is my liability limit?",
            "can I work with other clients?",
            "who owns the code and intellectual property?",
            "how much notice is required for termination?",
            "is there a non-compete clause?",
        ]

        def worker_search(i: int) -> tuple[int, float]:
            worker_client = TestClient(app)
            query = search_queries[i % len(search_queries)]
            t0 = time.time()
            resp = worker_client.post(
                "/api/v1/search",
                json={"document_id": seed_doc_id, "query": query, "top_k": 3},
            )
            return resp.status_code, time.time() - t0

        search_req_count = 30
        with ThreadPoolExecutor(max_workers=10) as pool:
            futures = [pool.submit(worker_search, i) for i in range(search_req_count)]
            for f in futures:
                code, dur = f.result()
                statuses_search.append(code)
                latencies_search.append(dur)

        total_time_search = time.time() - t_start
        success_search = sum(1 for s in statuses_search if s == 200)

        results["concurrent_search"] = {
            "total_requests": len(statuses_search),
            "successful_requests": success_search,
            "success_rate_pct": round((success_search / len(statuses_search)) * 100, 2),
            "total_elapsed_sec": round(total_time_search, 3),
            "throughput_rps": round(len(statuses_search) / total_time_search, 2),
            "latency": _calc_latency_stats(latencies_search),
        }

        # 4. Memory Profiling & Leak Test (15 sequential runs)
        mem_samples: List[float] = [_get_rss_mb()]
        for i in range(1, 16):
            client.post(
                "/api/v1/analyze",
                files={"file": (f"mem_check_{i}.txt", doc01_bytes, "text/plain")},
            )
            if i % 5 == 0:
                mem_samples.append(_get_rss_mb())

        gc.collect()
        post_gc_mem = _get_rss_mb()
        mem_delta = post_gc_mem - mem_samples[0]

        results["memory_profiling"] = {
            "initial_rss_mb": mem_samples[0],
            "sample_5_mb": mem_samples[1],
            "sample_10_mb": mem_samples[2],
            "sample_15_mb": mem_samples[3],
            "post_gc_rss_mb": post_gc_mem,
            "net_growth_mb": round(mem_delta, 2),
            "leak_detected": mem_delta > 500.0,
        }

    return results
