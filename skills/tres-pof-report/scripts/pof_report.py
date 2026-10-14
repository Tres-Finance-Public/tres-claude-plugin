#!/usr/bin/env python3
"""
TRES Proof of Funds (PoF) account balances export.

Exports one CSV row per token balance of every account in a PoF snapshot, using the
read-only TRES API PoF endpoints (/pof/snapshot-status, /pof/aggregate-account-balances,
/pof/find-account-balances). Python 3 standard library only.

The organization is the one the credentials belong to.

Credentials (environment only, never passed on the command line):
    TRES_CLIENT_ID + TRES_CLIENT_SECRET   organization API key (exchanged for a token), or
    TRES_API_TOKEN                        an existing bearer token
Optional:
    TRES_API_URL    default https://api.tres.finance
    TRES_AUTH_URL   default https://tres-finance.us.auth0.com/oauth/token

Usage:
    python3 -I pof_report.py --timestamp latest --check-only
    python3 -I pof_report.py --timestamp 2026-07-01T00:00:00Z --org-label nonco --out ~/Downloads

Exit codes:
    0 success, 1 error, 2 snapshot not found / not completed, 3 too many rows
"""

import argparse
import csv
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

DEFAULT_API_URL = "https://api.tres.finance"
DEFAULT_AUTH_URL = "https://tres-finance.us.auth0.com/oauth/token"
AUTH_AUDIENCE = "https://app.tres.finance"

DEFAULT_MAX_ROWS = 1_000_000  # Excel's sheet limit is 1,048,576 rows
DEFAULT_PAGE_SIZE = 2000  # account documents per request (pof-service caps at 20,000)
LATEST_LOOKBACK_DAYS = 7
NEAREST_WINDOW_DAYS = 3
TOP_NETWORKS_IN_SUMMARY = 10
REQUEST_TIMEOUT_SECONDS = 120
MAX_ATTEMPTS = 4
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_NO_SNAPSHOT = 2
EXIT_TOO_LARGE = 3

COLUMNS = [
    "timestamp",
    "network",
    "accountAddress",
    "blockNumber",
    "blockTimestamp",
    "custodianName",
    "source",
    "sourceAddressName",
    "sourceAddressType",
    "sourceOriginId",
    "tokenAddress",
    "amount",
    "symbol",
    "unitFiatPrice",
    "fiatValue",
    "fiat",
]
ACCOUNT_COLUMNS = COLUMNS[:10]
BALANCE_COLUMNS = COLUMNS[10:]


class ReportError(Exception):
    def __init__(self, message, exit_code=EXIT_ERROR, details=None):
        super().__init__(message)
        self.exit_code = exit_code
        self.details = details or {}


def log(message):
    print(message, file=sys.stderr, flush=True)


def require_secure_url(url, name):
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme == "https":
        return
    if parsed.scheme == "http" and parsed.hostname in LOCAL_HOSTS:
        return
    raise ReportError(f"{name} must use https:// (plain http is only allowed for localhost)")


def http_json(method, url, body=None, headers=None, form=False):
    """Send a request and return the parsed JSON. Numbers are kept as their original text."""
    headers = dict(headers or {})
    data = None
    if body is not None:
        if form:
            data = urllib.parse.urlencode(body).encode()
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        else:
            data = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
    headers.setdefault("Accept", "application/json")
    headers.setdefault("x-tres-source", "tres-pof-report-skill")

    for attempt in range(1, MAX_ATTEMPTS + 1):
        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
                raw = response.read()
            return json.loads(raw, parse_float=str, parse_int=str) if raw else None
        except urllib.error.HTTPError as error:
            detail = error.read().decode(errors="replace")[:500]
            retryable = error.code >= 500 or error.code == 429
            if not retryable or attempt == MAX_ATTEMPTS:
                raise ReportError(f"{method} {urllib.parse.urlparse(url).path} failed with HTTP {error.code}: {detail}")
        except (urllib.error.URLError, TimeoutError, ConnectionError) as error:
            if attempt == MAX_ATTEMPTS:
                raise ReportError(f"{method} {urllib.parse.urlparse(url).path} failed: {error}")
        backoff = 2**attempt
        log(f"  request failed (attempt {attempt}/{MAX_ATTEMPTS}), retrying in {backoff}s")
        time.sleep(backoff)
    raise ReportError("unreachable")


def get_bearer_token():
    token = os.environ.get("TRES_API_TOKEN")
    if token:
        return token

    client_id = os.environ.get("TRES_CLIENT_ID")
    client_secret = os.environ.get("TRES_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise ReportError(
            "Missing credentials: set TRES_CLIENT_ID and TRES_CLIENT_SECRET (organization API key) "
            "or TRES_API_TOKEN in the environment"
        )

    auth_url = os.environ.get("TRES_AUTH_URL", DEFAULT_AUTH_URL)
    require_secure_url(auth_url, "TRES_AUTH_URL")
    try:
        response = http_json(
            "POST",
            auth_url,
            {
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
                "audience": AUTH_AUDIENCE,
            },
            form=True,
        )
    except ReportError as error:
        # Never surface the auth response body: it may echo request details
        raise ReportError("Could not obtain a TRES API token: check TRES_CLIENT_ID / TRES_CLIENT_SECRET") from error

    access_token = (response or {}).get("access_token")
    if not access_token:
        raise ReportError("Could not obtain a TRES API token: check TRES_CLIENT_ID / TRES_CLIENT_SECRET")
    return access_token


class PofApi:
    def __init__(self, base_url, token):
        self.base_url = base_url.rstrip("/")
        self.headers = {"Authorization": f"Bearer {token}"}

    def post(self, path, body):
        return http_json("POST", f"{self.base_url}/pof/{path}", body, self.headers)

    def snapshot_status(self, timestamps_ms=None, start=None, end=None):
        if timestamps_ms:
            body = {"timestamps": [str(ms) for ms in timestamps_ms]}
        else:
            body = {"startDate": to_iso(start), "endDate": to_iso(end)}
        return self.post("snapshot-status", body) or {}

    def count_rows(self, timestamp, networks, sources):
        match = {"$expr": {"$eq": ["$timestamp", {"$toDate": to_ms(timestamp)}]}}
        if networks:
            match["network"] = {"$in": networks}
        if sources:
            match["source"] = {"$in": sources}
        pipeline = [
            {"$match": match},
            {"$group": {"_id": "$network", "documents": {"$sum": 1}, "rows": {"$sum": {"$size": "$balances"}}}},
        ]
        response = self.post("aggregate-account-balances", {"pipeline": pipeline}) or {}
        return response.get("results", [])

    def find_page(self, timestamp, networks, sources, limit, offset):
        body = {"timestamps": [to_iso(timestamp)], "limit": limit, "offset": offset}
        if networks:
            body["networks"] = networks
        if sources:
            body["sources"] = sources
        response = self.post("find-account-balances", body) or {}
        return response.get("results", [])


def to_ms(moment):
    return int(moment.timestamp() * 1000)


def to_iso(moment):
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def from_ms(ms):
    return datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc)


def parse_timestamp(value):
    if value.isdigit():
        return from_ms(value)
    try:
        moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ReportError(f"Invalid --timestamp {value!r}: use 'latest', ISO-8601 or epoch milliseconds") from error
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc)


def completed_snapshots(status):
    snapshots = status.get("snapshots") or {}
    return sorted(int(ms) for ms, info in snapshots.items() if info.get("isCompleted"))


def nearest_snapshots(api, moment):
    window = timedelta(days=NEAREST_WINDOW_DAYS)
    completed = completed_snapshots(api.snapshot_status(start=moment - window, end=moment + window))
    target = to_ms(moment)
    before = [ms for ms in completed if ms < target]
    after = [ms for ms in completed if ms > target]
    return {
        "before": to_iso(from_ms(before[-1])) if before else None,
        "after": to_iso(from_ms(after[0])) if after else None,
    }


def resolve_snapshot(api, requested):
    if requested == "latest":
        now = datetime.now(timezone.utc)
        completed = completed_snapshots(api.snapshot_status(start=now - timedelta(days=LATEST_LOOKBACK_DAYS), end=now))
        if not completed:
            raise ReportError(
                f"No completed PoF snapshot in the last {LATEST_LOOKBACK_DAYS} days", EXIT_NO_SNAPSHOT
            )
        return from_ms(completed[-1])

    moment = parse_timestamp(requested)
    ms = to_ms(moment)
    status = api.snapshot_status(timestamps_ms=[ms])
    if str(ms) in (status.get("missingSnapshots") or []):
        raise ReportError(
            f"{to_iso(moment)} is not a snapshot time for this organization's schedule",
            EXIT_NO_SNAPSHOT,
            {"nearest": nearest_snapshots(api, moment)},
        )

    info = (status.get("snapshots") or {}).get(str(ms)) or {}
    if not info.get("isCompleted"):
        reason = "is still in progress" if info.get("networksInProgress") else "has no collected data"
        raise ReportError(
            f"The snapshot at {to_iso(moment)} {reason}",
            EXIT_NO_SNAPSHOT,
            {
                "networksCompleted": len(info.get("networksCompleted") or []),
                "networksInProgress": info.get("networksInProgress") or [],
                "nearest": nearest_snapshots(api, moment),
            },
        )
    return moment


def suggest_split(by_network, max_rows):
    """Greedy first-fit of networks into groups of at most max_rows rows."""
    groups = []
    for entry in sorted(by_network, key=lambda item: item["rows"], reverse=True):
        for group in groups:
            if group["rows"] + entry["rows"] <= max_rows:
                group["networks"].append(entry["network"])
                group["rows"] += entry["rows"]
                break
        else:
            groups.append({"networks": [entry["network"]], "rows": entry["rows"]})
    return groups


def check_size(api, snapshot, networks, sources, max_rows):
    try:
        results = api.count_rows(snapshot, networks, sources)
    except ReportError as error:
        log(f"  row count unavailable ({error}); the export will stop if it exceeds {max_rows:,} rows")
        return None

    by_network = sorted(
        ({"network": item["_id"], "documents": int(item["documents"]), "rows": int(item["rows"])} for item in results),
        key=lambda item: item["rows"],
        reverse=True,
    )
    total_rows = sum(item["rows"] for item in by_network)
    size = {
        "rows": total_rows,
        "documents": sum(item["documents"] for item in by_network),
        "networks": len(by_network),
        "topNetworks": by_network[:TOP_NETWORKS_IN_SUMMARY],
    }
    if total_rows > max_rows:
        oversized = [item["network"] for item in by_network if item["rows"] > max_rows]
        raise ReportError(
            f"The export would have {total_rows:,} rows, above the {max_rows:,} row limit",
            EXIT_TOO_LARGE,
            {
                **size,
                "suggestedSplit": suggest_split(by_network, max_rows),
                "networksAboveLimitOnTheirOwn": oversized,
            },
        )
    return size


def cell(value):
    return "" if value is None else value


def export(api, snapshot, networks, sources, max_rows, page_size, out_path):
    tmp_path = out_path + ".part"
    rows = documents = missing_price = 0
    fiat_by_source = {}
    networks_seen = set()

    try:
        with open(tmp_path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(COLUMNS)
            offset = 0
            while True:
                page = api.find_page(snapshot, networks, sources, page_size, offset)
                for account in page:
                    documents += 1
                    networks_seen.add(account.get("network"))
                    account_cells = [cell(account.get(column)) for column in ACCOUNT_COLUMNS]
                    for balance in account.get("balances") or []:
                        rows += 1
                        if rows > max_rows:
                            raise ReportError(
                                f"Export exceeded the {max_rows:,} row limit; aborted and removed the partial file",
                                EXIT_TOO_LARGE,
                            )
                        writer.writerow(account_cells + [cell(balance.get(column)) for column in BALANCE_COLUMNS])
                        if balance.get("unitFiatPrice") is None:
                            missing_price += 1
                        fiat_value = balance.get("fiatValue")
                        if fiat_value is not None:
                            source = account.get("source") or ""
                            fiat_by_source[source] = fiat_by_source.get(source, 0.0) + float(fiat_value)
                log(f"  fetched {documents:,} accounts / {rows:,} rows")
                if len(page) < page_size:
                    break
                offset += page_size
        os.replace(tmp_path, out_path)
    except BaseException:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise

    return {
        "file": out_path,
        "rows": rows,
        "documents": documents,
        "networks": len(networks_seen),
        "rowsMissingPrice": missing_price,
        "fiatValueBySource": {source: round(total, 2) for source, total in sorted(fiat_by_source.items())},
    }


def output_file_name(org_label, snapshot):
    stamp = snapshot.strftime("%Y-%m-%d") if snapshot.strftime("%H%M%S") == "000000" else snapshot.strftime("%Y-%m-%dT%H%M%SZ")
    prefix = f"{org_label}-pof" if org_label else "pof"
    return f"{prefix}.accountBalances.{stamp}.csv"


def split_list(value):
    return [item.strip() for item in value.split(",") if item.strip()] if value else None


def main():
    parser = argparse.ArgumentParser(description="Export TRES PoF account balances to CSV")
    parser.add_argument("--timestamp", default="latest", help="'latest', ISO-8601 (UTC) or epoch milliseconds")
    parser.add_argument("--out", default=".", help="output directory (default: current directory)")
    parser.add_argument("--org-label", help="organization name used in the file name, e.g. nonco")
    parser.add_argument("--networks", help="comma-separated networks to include")
    parser.add_argument("--sources", help="comma-separated sources to include")
    parser.add_argument("--max-rows", type=int, default=DEFAULT_MAX_ROWS)
    parser.add_argument("--page-size", type=int, default=DEFAULT_PAGE_SIZE)
    parser.add_argument("--check-only", action="store_true", help="resolve the snapshot and count rows, then stop")
    args = parser.parse_args()

    try:
        if args.org_label and not all(char.isalnum() or char in "-_" for char in args.org_label):
            raise ReportError("--org-label may only contain letters, digits, '-' and '_'")
        if args.max_rows <= 0 or not 0 < args.page_size <= 20000:
            raise ReportError("--max-rows must be positive and --page-size between 1 and 20000")

        base_url = os.environ.get("TRES_API_URL", DEFAULT_API_URL)
        require_secure_url(base_url, "TRES_API_URL")
        api = PofApi(base_url, get_bearer_token())
        networks = split_list(args.networks)
        sources = split_list(args.sources)

        log(f"Resolving snapshot '{args.timestamp}'...")
        snapshot = resolve_snapshot(api, args.timestamp)
        log(f"  snapshot: {to_iso(snapshot)}")

        log("Counting rows...")
        size = check_size(api, snapshot, networks, sources, args.max_rows)
        if size:
            log(f"  {size['rows']:,} rows across {size['documents']:,} accounts on {size['networks']} networks")

        summary = {"status": "ok", "snapshot": to_iso(snapshot), "maxRows": args.max_rows, "expected": size}
        if not args.check_only:
            out_dir = os.path.abspath(os.path.expanduser(args.out))
            os.makedirs(out_dir, exist_ok=True)
            out_path = os.path.join(out_dir, output_file_name(args.org_label, snapshot))
            log(f"Exporting to {out_path}...")
            summary["export"] = export(api, snapshot, networks, sources, args.max_rows, args.page_size, out_path)
        print(json.dumps(summary, indent=2))
        return EXIT_OK
    except ReportError as error:
        print(json.dumps({"status": "error", "message": str(error), **error.details}, indent=2))
        return error.exit_code
    except KeyboardInterrupt:
        print(json.dumps({"status": "error", "message": "interrupted"}))
        return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())
