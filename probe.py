#!/usr/bin/env python3
"""Independent TWSE/TPEx MIS closing-auction probe for GitHub Actions."""

from __future__ import annotations

import argparse
import concurrent.futures
import csv
import http.client
import json
import os
import re
import socket
import statistics
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import zipfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import freshness
import convergence
import official_quotes
import tradable

TZ = ZoneInfo("Asia/Taipei")
MIS = "https://mis.twse.com.tw/stock/api/getStockInfo.jsp"
UNIVERSE_SOURCES = (
    ("TWSE", "tse", "https://openapi.twse.com.tw/v1/opendata/t187ap03_L",
     "公司代號", "公司簡稱"),
    ("TPEx", "otc", "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O",
     "SecuritiesCompanyCode", "CompanyAbbreviation"),
)
TWSE_CLOSE = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
TPEX_CLOSE = "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes"
BATCH_SIZE = 50
CONCURRENCY = 5
FIELDS = ("c", "n", "z", "pz", "t", "v", "tv", "s", "d")
FIXED_PROBE = (
    ("tse", "2330"), ("tse", "2317"), ("tse", "2454"),
    ("tse", "1341"), ("tse", "1410"),
    ("otc", "1240"), ("otc", "1781"), ("otc", "1813"),
)
HEADERS = {
    "Accept": "application/json,text/html;q=0.9,*/*;q=0.8",
    "User-Agent": "Mozilla/5.0 (compatible; tw-close-auction-mis-probe/1.0)",
    "Referer": "https://mis.twse.com.tw/stock/index.jsp",
    "Cache-Control": "no-cache",
}


def now_tpe() -> datetime:
    return datetime.now(TZ)


def iso(dt: datetime | None = None) -> str:
    return (dt or now_tpe()).astimezone(TZ).isoformat(timespec="milliseconds")


def target(date: str, clock: str) -> datetime:
    return datetime.fromisoformat(f"{date}T{clock}").replace(tzinfo=TZ)


def wait_until(dt: datetime) -> None:
    while True:
        remaining = dt.timestamp() - time.time()
        if remaining <= 0:
            return
        time.sleep(min(remaining, 30))


def get_bytes(url: str, timeout: int = 30, headers: dict | None = None) -> tuple[int, bytes]:
    request = urllib.request.Request(url, headers=headers or HEADERS)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.status, response.read()


def parse_universe_rows(rows: object, market_name: str, ex: str,
                        code_key: str, name_key: str) -> list[dict]:
    if not isinstance(rows, list):
        raise RuntimeError(f"{market_name} official universe is not a JSON array")
    parsed: list[dict] = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        code = str(item.get(code_key, "")).strip()
        name = str(item.get(name_key, "")).strip()
        # Normal listed/OTC company shares use four-digit codes. 91xx are TDRs,
        # not ordinary listed/OTC company shares for this strategy universe.
        if (re.fullmatch(r"\d{4}", code) and not code.startswith(("0", "91"))
                and name):
            symbol={"code": code, "name": name, "market": market_name, "ex": ex}
            listing=item.get('上市日期') or item.get('DateOfListing')
            if listing:symbol['listing_date']=listing
            legal_name=item.get('公司名稱') or item.get('CompanyName')
            if legal_name:symbol['company_name']=legal_name
            parsed.append(symbol)
    return parsed


def fetch_universe(output: Path | None = None) -> list[dict]:
    universe: list[dict] = []
    for market_name, ex, url, code_key, name_key in UNIVERSE_SOURCES:
        for attempt in range(3):
            began,tick=iso(),time.monotonic()
            event={}
            try:
                status,raw=get_bytes(url,35,HEADERS)
                event={'market':market_name,'attempt':attempt+1,'started_at':began,
                       'finished_at':iso(),'http_status':status,'raw_bytes':len(raw),
                       'latency_ms':round((time.monotonic()-tick)*1000,3)}
                if output:(output/f'universe_source_{market_name}.json').write_bytes(raw)
                break
            except (http.client.HTTPException,urllib.error.URLError,TimeoutError,OSError) as exc:
                event={'market':market_name,'attempt':attempt+1,'started_at':began,
                       'finished_at':iso(),'error':f'{type(exc).__name__}:{exc}'}
                if attempt==2 or isinstance(exc,urllib.error.HTTPError) and exc.code in (403,429):raise
                time.sleep(.5*(attempt+1))
            finally:
                print(json.dumps({'universe_fetch':event},ensure_ascii=False),flush=True)
                if output:
                    with (output/'universe_fetch_attempts.jsonl').open('a') as log:
                        log.write(json.dumps(event,ensure_ascii=False)+'\n')
        if status != 200:
            raise RuntimeError(f"{market_name} official universe HTTP {status}")
        try:
            rows = json.loads(raw.decode("utf-8-sig"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"{market_name} official universe JSON parse failed: {exc}") from exc
        market_rows = parse_universe_rows(rows, market_name, ex, code_key, name_key)
        found = len(market_rows)
        universe.extend(market_rows)
        if found < 300:
            raise RuntimeError(f"{market_name} official universe parsed only {found} stocks")
    keys = {(x["ex"], x["code"]) for x in universe}
    if len(keys) != len(universe) or len(universe) < 1000 or ("tse", "2330") not in keys:
        raise RuntimeError(f"Official universe integrity failed: rows={len(universe)}, unique={len(keys)}")
    return sorted(universe, key=lambda x: (x["ex"], x["code"]))


@dataclass
class FetchResult:
    requested_at: str
    received_at: str
    latency_ms: int
    http_status: int | None
    retry: int
    error: str | None
    raw_body: str | None
    response: dict | None
    attempts: list[dict] = field(default_factory=list)


def fetch_mis(symbols: list[dict], retry: int = 1, timeout: int = 20, deadline: datetime | None = None) -> FetchResult:
    last: FetchResult | None = None
    attempts = []
    for attempt in range(retry + 1):
        started = now_tpe()
        if deadline and started >= deadline:
            return FetchResult(iso(started),iso(started),0,None,attempt,
                               'CAPTURE_DEADLINE_NO_REQUEST',None,None,list(attempts))
        tick = time.monotonic()
        params = urllib.parse.urlencode({
            "ex_ch": "|".join(f'{x["ex"]}_{x["code"]}.tw' for x in symbols),
            "json": "1", "delay": "0", "_": f"{int(started.timestamp() * 1000)}-{attempt}",
        })
        status = None
        raw = None
        body = None
        error = None
        try:
            request_timeout=min(timeout,max(.1,(deadline-started).total_seconds())) if deadline else timeout
            status, raw_bytes = get_bytes(f"{MIS}?{params}", request_timeout, HEADERS)
            raw = raw_bytes.decode("utf-8", "replace")
            if not raw.strip():
                error = "MIS_EMPTY_BODY"
            else:
                try:
                    body = json.loads(raw)
                except json.JSONDecodeError as exc:
                    error = f"JSON_PARSE_ERROR:{exc}"
            if status != 200:
                error = f"HTTP_{status}"
            elif not error and (not isinstance(body, dict) or body.get("rtcode") != "0000"):
                error = f"MIS_{body.get('rtcode', 'NO_RTCODE') if isinstance(body, dict) else 'NO_RTCODE'}"
        except urllib.error.HTTPError as exc:
            status = exc.code
            raw = exc.read().decode("utf-8", "replace")
            error = f"HTTP_{exc.code}"
        except (http.client.HTTPException, urllib.error.URLError, TimeoutError, socket.timeout, OSError) as exc:
            error = f"{type(exc).__name__}:{exc}"
        last = FetchResult(iso(started), iso(), round((time.monotonic() - tick) * 1000),
                           status, attempt, error, raw, body)
        if deadline and datetime.fromisoformat(last.received_at)>deadline:
            last.error='RESPONSE_AFTER_CAPTURE_DEADLINE'+(':'+error if error else '')
        attempts.append(asdict(last))
        last.attempts = list(attempts)
        if not error:
            return last
        if status in (403,429): return last
        if attempt < retry:
            time.sleep(0.5 * (attempt + 1))
    assert last is not None
    return last


def analyze(symbols: list[dict], result: FetchResult) -> dict:
    expected = {f'{x["ex"]}:{x["code"]}' for x in symbols}
    seen: set[str] = set()
    duplicate: list[str] = []
    empty: list[str] = []
    items = result.response.get("msgArray", []) if isinstance(result.response, dict) and not result.error else []
    for item in items if isinstance(items, list) else []:
        key = f'{item.get("ex")}:{item.get("c")}'
        if key not in expected:
            continue
        if key in seen:
            duplicate.append(key)
        seen.add(key)
        if not item.get("c") or not item.get("n"):
            empty.append(key)
    return {"returned_count": len(seen), "missing": sorted(expected - seen),
            "duplicate": duplicate, "empty": empty}


def snapshot(phase: str, planned: datetime, universe: list[dict], output: Path, deadline: datetime | None = None) -> dict:
    groups = [universe[i:i + BATCH_SIZE] for i in range(0, len(universe), BATCH_SIZE)]
    started = now_tpe()
    records: list[dict] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
        futures = [(i + 1, group, pool.submit(fetch_mis, group,1,20,deadline)) for i, group in enumerate(groups)]
        for batch_no, group, future in futures:
            result = future.result()
            row = {"phase": phase, "planned_at": iso(planned), "batch_no": batch_no,
                   "expected_count": len(group), "symbols": group, **asdict(result)}
            row.update(analyze(group, result))
            records.append(row)
    raw_path = output / ({"preclose": "preclose_raw.jsonl", "close": "close_raw.jsonl",
                         "delayed_close": "delayed_close_raw.jsonl"}.get(phase, f"{phase}_raw.jsonl"))
    with raw_path.open('a' if phase.endswith('_targeted_retry') else 'w', encoding='utf-8') as file:
        file.write("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in records))
    finished = now_tpe()
    latencies = sorted(x["latency_ms"] for x in records)
    successful = set()
    for record in records:
        expected = {f'{x["ex"]}:{x["code"]}' for x in record["symbols"]}
        successful.update(expected - set(record["missing"]) - set(record["empty"]))
    metrics = {
        "phase": phase, "stock_universe_count": len(universe), "batch_count": len(groups),
        "batch_size": BATCH_SIZE, "concurrency": CONCURRENCY,
        "first_request_started_at": min((x["requested_at"] for x in records), default=None),
        "last_response_received_at": max((x["received_at"] for x in records), default=None),
        "wall_time_seconds": round((finished - started).total_seconds(), 3),
        "fastest_batch_ms": latencies[0] if latencies else None,
        "average_batch_ms": round(statistics.mean(latencies), 1) if latencies else None,
        "median_batch_ms": round(statistics.median(latencies), 1) if latencies else None,
        "p95_batch_ms": latencies[max(0, int(len(latencies) * .95 + .999) - 1)] if latencies else None,
        "slowest_batch_ms": latencies[-1] if latencies else None,
        "success_count": len(successful), "missing_count": len(universe) - len(successful),
        "missing_codes": sorted({f'{x["ex"]}:{x["code"]}' for x in universe} - successful),
        "http_errors": sum(x["http_status"] != 200 for x in records),
        "timeouts": sum("timeout" in (x["error"] or "").lower() for x in records),
        "retries": sum(x["retry"] for x in records),
        "empty_count": sum(len(x["empty"]) for x in records),
        "duplicate_count": sum(len(x["duplicate"]) for x in records),
        "insufficient_batches": [x["batch_no"] for x in records if x["returned_count"] < x["expected_count"]],
        "symbol_set_equal": len(successful) == len(universe),
    }
    return {"records": records, "metrics": metrics}


def reference_capture(phase, date, universe, output, deadline):
    planned = target(date, convergence.REFERENCE_TIMES[phase])
    wait_until(planned)
    if now_tpe() > planned+timedelta(milliseconds=750):
        # Keep the missed attempt explicit. Targeted replacement observations are
        # separately labelled and cannot masquerade as the scheduled A/B instant.
        stamp = iso()
        rows = []
        for i in range(0, len(universe), BATCH_SIZE):
            group = universe[i:i+BATCH_SIZE]
            result = FetchResult(stamp, stamp, 0, None, 0, 'REFERENCE_NOT_SAMPLED', None, None)
            rows.append({'phase': phase, 'planned_at': iso(planned), 'batch_no': i//BATCH_SIZE+1,
                         'expected_count': len(group), 'symbols': group, **asdict(result), **analyze(group, result)})
        (output/(phase+'_raw.jsonl')).write_text(''.join(json.dumps(r, ensure_ascii=False)+'\n' for r in rows))
        return {'records': rows, 'metrics': {'phase': phase, 'status': 'NOT_SAMPLED',
                'success_count': 0, 'stock_universe_count': len(universe), 'symbol_set_equal': False}}
    return snapshot(phase, planned, universe, output, target(date, deadline))


def targeted_retries(kind, date, snapshots, universe, output, probe_rows=()):
    deadline = target(date, convergence.DEADLINES[kind])
    rounds = []
    while now_tpe() < deadline:
        affected = convergence.unresolved(date, snapshots+rounds, universe, kind, probe_rows)
        if not affected:
            break
        # A 403/429 stops retrying; do not turn a freshness study into a rate-limit loop.
        if any(r.get('http_status') in (403, 429) for s in snapshots+rounds for r in s['records']):
            break
        planned = now_tpe()
        replacement = snapshot(kind+'_targeted_retry', planned, affected, output, deadline)
        replacement['metrics']['retry_round'] = len(rounds)+1
        replacement['metrics']['affected_symbols'] = [s['ex']+':'+s['code'] for s in affected]
        rounds.append(replacement)
        wait_until(min(now_tpe()+timedelta(seconds=5), deadline))
    return rounds


def per_second_probe(date: str, window_name: str, start: str, end: str,
                     symbols: list[dict], output: Path, checkpoints=()) -> list[dict]:
    ticks = freshness.planned_ticks(date,start,end,checkpoints)
    rows: list[dict] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=24) as pool:
        futures: list[tuple[datetime, concurrent.futures.Future]] = []
        for tick in ticks:
            wait_until(tick)
            late = time.time() - tick.timestamp()
            if late > .75:
                rows.append({"window": window_name, "planned_at": iso(tick),
                             "symbols":symbols,
                             "error": "SCHEDULER_LATE_NO_REQUEST", "late_ms": round(late * 1000)})
            else:
                futures.append((tick, pool.submit(fetch_mis, symbols, 0, 18)))
        for tick, future in futures:
            result = future.result()
            rows.append({"window": window_name, "planned_at": iso(tick), **asdict(result),
                         "symbols":symbols,
                         **analyze(symbols, result)})
    rows.sort(key=lambda x: x["planned_at"])
    path = output / "probe_raw.jsonl"
    with path.open("a", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return rows


def normalized_csv(snapshots: list[dict], probe_rows: list[dict], output: Path) -> None:
    columns = ("record_type", "phase", "planned_at", "requested_at", "received_at",
               "batch_no", "market", "code", "name", *FIELDS, "error")
    with (output / "normalized.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns)
        writer.writeheader()
        for snap in snapshots:
            for record in snap["records"]:
                items = record["response"].get("msgArray", []) if isinstance(record["response"], dict) else []
                lookup = {(x.get("ex"), x.get("c")): x for x in items if isinstance(x, dict)}
                for symbol in record["symbols"]:
                    item = lookup.get((symbol["ex"], symbol["code"]), {})
                    writer.writerow({"record_type": "snapshot", "phase": record["phase"],
                        "planned_at": record["planned_at"], "requested_at": record["requested_at"],
                        "received_at": record["received_at"], "batch_no": record["batch_no"],
                        "market": symbol["market"], "code": symbol["code"], "name": symbol["name"],
                        **{k: item.get(k, "") for k in FIELDS},
                        "error": record["error"] or ("MISSING_SYMBOL" if not item else "")})
        for record in probe_rows:
            items = record.get("response", {}).get("msgArray", []) if isinstance(record.get("response"), dict) else []
            for item in items:
                writer.writerow({"record_type": "probe", "phase": record["window"],
                    "planned_at": record["planned_at"], "requested_at": record.get("requested_at"),
                    "received_at": record.get("received_at"), "market": item.get("ex"),
                    "code": item.get("c"), "name": item.get("n"),
                    **{k: item.get(k, "") for k in FIELDS}, "error": record.get("error")})
    # Complete parsed outer/nested/server fields; missing values stay null/empty.
    all_records=[r for snap in snapshots for r in snap['records']]+probe_rows
    date=all_records[0]['planned_at'][:10] if all_records else now_tpe().date().isoformat()
    expanded=freshness.observations(all_records,date)
    if expanded:
        with (output/'normalized_freshness.csv').open('w',encoding='utf-8-sig',newline='') as fh:
            writer=csv.DictWriter(fh,fieldnames=list(expanded[0]));writer.writeheader()
            for row in expanded:
                writer.writerow({k:json.dumps(v,ensure_ascii=False) if isinstance(v,dict) else v for k,v in row.items()})


def official_validation(date: str, probe_symbols: list[dict], close_snapshot: dict, output: Path) -> dict:
    return official_quotes.validate(date,probe_symbols,[close_snapshot],output,get_bytes)




def github_issue(body: str) -> None:
    token, repo, number = os.getenv("GITHUB_TOKEN"), os.getenv("GITHUB_REPOSITORY"), os.getenv("STATUS_ISSUE_NUMBER")
    if not (token and repo and number):
        return
    data = json.dumps({"body": body}).encode()
    req = urllib.request.Request(f"https://api.github.com/repos/{repo}/issues/{number}", data=data, method="PATCH",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
                 "X-GitHub-Api-Version": "2022-11-28", "Content-Type": "application/json",
                 "User-Agent": "tw-close-auction-mis-probe"})
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            response.read()
    except Exception as exc:
        print(f"::warning::Issue update failed: {type(exc).__name__}: {exc}", flush=True)


def issue_body(headline: str, date: str, started: str, phase: str, universe_count="尚未取得", summary=None) -> str:
    summary = summary or {}
    pre, close = summary.get("preclose", {}), summary.get("close", {})
    return f"""# {headline}

- trade date：`{date}`
- runner startedAt：`{started}`
- phase：`{phase}`
- 股票池數量：`{universe_count}`
- 13:25 成功數／總數：`{pre.get('success_count', '—')}/{pre.get('stock_universe_count', '—')}`
- 13:30 成功數／總數：`{close.get('success_count', '—')}/{close.get('stock_universe_count', '—')}`
- 13:33 補抓數：`{summary.get('delayed_close', {}).get('success_count', '—')}`
- 13:25 全市場耗時：`{pre.get('wall_time_seconds', '—')} 秒`
- 13:30 全市場耗時：`{close.get('wall_time_seconds', '—')} 秒`
- missing：`{pre.get('missing_count', '—')} / {close.get('missing_count', '—')}`
- timeout：`{pre.get('timeouts', '—')} / {close.get('timeouts', '—')}`
- retry：`{pre.get('retries', '—')} / {close.get('retries', '—')}`
- research ±3%：`{summary.get('candidate_count', '—')}`；validated=false，正式訊號未產生。
- 官方核對結果：`observational_only_unverified`
- Artifact 名稱：`mis-probe-{os.getenv('GITHUB_RUN_ID', 'local')}`

> 2026-09-29：`missing / incomplete`。本 Issue 只顯示本 repo 的獨立探針狀態，不代表任何 Production 已變更。
"""


def package(output: Path, date: str) -> Path:
    path = output.parent / f"mis-probe-{date}.zip"
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for file in sorted(output.iterdir()):
            if file.is_file():
                archive.write(file, file.name)
    return path


def dry_run(output: Path) -> int:
    started = iso()
    date = now_tpe().date().isoformat()
    github_issue(issue_body("🟡 DRY RUNNING", date, started, "fetch_universe"))
    company = fetch_universe(output)
    universe,universe_audit = tradable.build(date,company,output,get_bytes)
    probe = [x for x in universe if (x["ex"], x["code"]) in FIXED_PROBE]
    result = fetch_mis(probe, 0, 20)
    row = {"mode": "dry-run", "started_at": started, "finished_at": iso(),
           "stock_universe_count": len(universe), "probe_symbols": probe,
           "company_universe_count":len(company),"universe_audit_status":universe_audit['status'],
           "mis": asdict(result), "analysis": analyze(probe, result),
           "note": "Connectivity only. No 13:25/13:30 data or strategy signals."}
    (output / "dry_run.json").write_text(json.dumps(row, ensure_ascii=False, indent=2), encoding="utf-8")
    (output / "run_summary.json").write_text(json.dumps(row, ensure_ascii=False, indent=2), encoding="utf-8")
    (output / "candidates.json").write_text(json.dumps({"status": "NOT_GENERATED", "reason": "dry-run"}, indent=2), encoding="utf-8")
    (output/'dual_snapshot_plan.json').write_text(json.dumps(convergence.plan(date), ensure_ascii=False, indent=2))
    (output/'freshness_schedule.json').write_text(json.dumps({
        'preclose':[iso(x) for x in freshness.planned_ticks(date,'13:24:50','13:25:10',freshness.PRECLOSE_CHECKPOINTS)],
        'close':[iso(x) for x in freshness.planned_ticks(date,'13:29:50','13:30:15',freshness.CLOSE_CHECKPOINTS)],
        'note':'Plan only; dry-run never fabricates scheduled market evidence.'},indent=2))
    dry_record={'phase':'dry_run','planned_at':result.requested_at,'symbols':probe,**asdict(result)}
    freshness.write_report(date,[{'records':[dry_record]}],[],probe,{'checks':[]},output)
    convergence.write_report(date, [{'records':[dry_record]}], [], probe, {'checks':[]}, output)
    package(output, date)
    good = (not result.error and result.http_status == 200 and
            not row['analysis']['missing'] and not row['analysis']['empty'] and
            len(probe) >= 8)
    github_issue(issue_body("🧪 DRY RUN SUCCESS" if good else "❌ DRY RUN FAILED",
                            date, started, "completed", len(universe)))
    return 0 if good else 1


def live(output: Path) -> int:
    runner_started = datetime.fromisoformat(os.environ['RUNNER_STARTED_AT']) if os.getenv('RUNNER_STARTED_AT') else now_tpe()
    date = runner_started.date().isoformat()
    github_issue(issue_body("🟡 RUNNING", date, iso(runner_started), "starting"))
    if runner_started > target(date, "13:24:45"):
        summary = {"status": "failed_late_start", "runner_started_at": iso(runner_started),
                   "cutoff": iso(target(date, "13:24:45")),
                   "reason": "Runner started after 13:24:45; no backfill is permitted."}
        (output / "run_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        package(output, date)
        github_issue(issue_body("❌ FAILED", date, iso(runner_started), "failed_late_start"))
        return 2
    company = fetch_universe(output)
    if now_tpe() > target(date, "13:24:45"):
        raise RuntimeError("failed_late_ready: official universe was not ready by 13:24:45; no preclose backfill")
    universe,universe_audit = tradable.build(date,company,output,get_bytes)
    (output / "universe.json").write_text(json.dumps(universe, ensure_ascii=False, indent=2), encoding="utf-8")
    probe_symbols = [x for x in universe if (x["ex"], x["code"]) in FIXED_PROBE]
    if len(probe_symbols) < 8:
        raise RuntimeError(f"Only {len(probe_symbols)} fixed probe symbols remain in official universe")
    if now_tpe() > target(date, "13:24:45"):
        raise RuntimeError("failed_late_ready: official universe was not ready by 13:24:45; no preclose backfill")
    github_issue(issue_body("🟡 RUNNING", date, iso(runner_started), "waiting_preclose", len(universe)))

    wait_until(target(date, "13:24:50"))
    if now_tpe() > target(date, "13:24:50") + timedelta(milliseconds=750):
        raise RuntimeError("failed_late_capture: preclose start missed; no backfill")
    github_issue(issue_body("🟡 RUNNING", date, iso(runner_started), "preclose_capture", len(universe)))
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        pre_future = pool.submit(snapshot, "preclose", target(date, "13:24:50"), universe, output)
        probe1_future = pool.submit(per_second_probe, date, "preclose_window", "13:24:50", "13:25:10", probe_symbols, output, freshness.PRECLOSE_CHECKPOINTS)
        pre = pre_future.result()
        probe_rows = probe1_future.result()

    (output/'dual_snapshot_plan.json').write_text(json.dumps(convergence.plan(date), ensure_ascii=False, indent=2))
    github_issue(issue_body("🟡 RUNNING", date, iso(runner_started), "pre_reference_A", len(universe)))
    pre_a = reference_capture('pre_reference_A', date, universe, output, '13:28:15')
    github_issue(issue_body("🟡 RUNNING", date, iso(runner_started), "pre_reference_B", len(universe)))
    pre_b = reference_capture('pre_reference_B', date, universe, output, '13:29:30')
    pre_retries = targeted_retries('pre', date, [pre_a, pre_b], universe, output, probe_rows)

    wait_until(target(date, "13:29:50"))
    github_issue(issue_body("🟡 RUNNING", date, iso(runner_started), "close_probe_research", len(universe)))
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        probe2_future = pool.submit(per_second_probe, date, "close_window", "13:29:50", "13:30:15", probe_symbols, output, freshness.CLOSE_CHECKPOINTS)
        github_issue(issue_body("🟡 RUNNING", date, iso(runner_started), "close_reference_A", len(universe)))
        close_a = reference_capture('close_reference_A', date, universe, output, '13:33:20')
        github_issue(issue_body("🟡 RUNNING", date, iso(runner_started), "close_reference_B", len(universe)))
        close_b = reference_capture('close_reference_B', date, universe, output, '13:35:00')
        probe_rows.extend(probe2_future.result())
    close_retries = targeted_retries('close', date, [close_a, close_b], universe, output, probe_rows)
    snapshots = [pre, pre_a, pre_b, *pre_retries, close_a, close_b, *close_retries]
    github_issue(issue_body("🟡 RUNNING", date, iso(runner_started), "validation", len(universe)))
    normalized_csv(snapshots, probe_rows, output)
    performance = {x["metrics"]["phase"]: x["metrics"] for x in snapshots if not x['metrics']['phase'].endswith('_targeted_retry')}
    performance['targeted_retry_rounds'] = [x['metrics'] for x in pre_retries+close_retries]
    (output / "performance_report.json").write_text(json.dumps(performance, ensure_ascii=False, indent=2), encoding="utf-8")
    errors = {"snapshot_errors": [{"phase": r["phase"], "batch": r["batch_no"], "error": r["error"],
               "missing": r["missing"], "empty": r["empty"], "duplicate": r["duplicate"]}
               for snap in snapshots for r in snap["records"] if r["error"] or r["missing"] or r["empty"] or r["duplicate"]],
              "probe_errors": [{"planned_at": r["planned_at"], "error": r.get("error"),
                                "missing":r.get('missing',[]), "empty":r.get('empty',[])}
               for r in probe_rows if r.get("error") or r.get('missing') or r.get('empty') or r.get('duplicate')]}
    (output / "error_missing_report.json").write_text(json.dumps(errors, ensure_ascii=False, indent=2), encoding="utf-8")
    selected = convergence.build_report(date, snapshots, probe_rows, universe, {'checks': []})
    validation = official_quotes.validate(date, universe, snapshots, output, get_bytes,
                                         selected_closes=selected['securities'])
    freshness_report = freshness.write_report(date, snapshots, probe_rows, universe, validation, output)
    dual = convergence.write_report(date, snapshots, probe_rows, universe, validation, output)
    # Research convergence and raw acquisition are separate outcomes. Pending
    # official publication is not a capture error, nor is no new closing trade.
    primary = [pre, pre_a, pre_b, close_a, close_b]
    raw_complete = all(x['metrics']['symbol_set_equal'] for x in primary) and not errors['probe_errors']
    summary = {"status": "success_raw_capture" if raw_complete and universe_audit['status']=='OFFICIAL_SOURCES_DATE_CHECKED' else "partial",
               "trade_date": date, "runner_started_at": iso(runner_started), "finished_at": iso(),
               "universe_count": len(universe), "company_universe_count": len(company),
               "universe_audit_status": universe_audit['status'], "exclusion_count": universe_audit['excluded_symbol_count'],
               "snapshots": performance, 'capture_architecture': convergence.VERSION,
               "probe_scheduled_count": len(probe_rows), "official_validation": validation["status"],
               "candidate_count": dual['research_candidate_count'], 'research_calculable_count': dual['research_calculable_count'],
               'candidate_status': 'RESEARCH_ONLY', 'validated': False,
               "artifact": f"mis-probe-{os.getenv('GITHUB_RUN_ID', 'local')}"}
    summary['freshness'] = {k:freshness_report[k] for k in ('status','p_before_validated_count','p_close_validated_count','both_validated_count')}
    summary['freshness']['confirmed_candidate_count'] = sum(v['p_before_freshness_status']=='confirmed_candidate' for v in freshness_report['securities'])
    summary['convergence'] = {k:v for k,v in dual.items() if k.endswith('_count') or k in ('status','version','validated')}
    (output / "run_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    package(output, date)
    headline = "✅ SUCCESS" if summary["status"] == "success_raw_capture" else "⚠️ PARTIAL"
    github_issue(issue_body(headline, date, iso(runner_started), "completed", len(universe), summary))
    return 0 if headline == "✅ SUCCESS" else 3


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("live", "dry-run"), default="dry-run")
    parser.add_argument("--output", type=Path, default=Path("results"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    try:
        return dry_run(args.output) if args.mode == "dry-run" else live(args.output)
    except Exception as exc:
        date, started = now_tpe().date().isoformat(), iso()
        failure = {"status": "failed", "error": f"{type(exc).__name__}: {exc}", "at": started}
        (args.output / "run_summary.json").write_text(json.dumps(failure, ensure_ascii=False, indent=2), encoding="utf-8")
        package(args.output, date)
        github_issue(issue_body("❌ FAILED", date, started, f"{type(exc).__name__}: {exc}"))
        print(json.dumps(failure, ensure_ascii=False), flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
