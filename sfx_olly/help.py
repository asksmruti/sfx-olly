"""Built-in, offline help topics. Usage: `sfx-olly help [topic]`."""

from __future__ import annotations

import difflib

from rich.console import Console
from rich.markdown import Markdown
from rich.table import Table

TOPICS: dict[str, tuple[str, str]] = {
    "quickstart": (
        "Install, configure and run your first query",
        """
# Quickstart

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .            # or: pip install -r requirements.txt
cp .env.example .env        # then edit SFX_TOKEN and SFX_REALM
sfx-olly metrics search "name:cpu.*" --limit 10
```

Without installing the entry point use `python -m sfx_olly ...`.
Global flag `-o json` prints raw API JSON instead of tables.
Global flag `-v` prints each API endpoint, request body and timing (token never shown),
e.g. `sfx-olly -v query cpu.utilization`.
""",
    ),
    "config": (
        "Environment variables and .env file",
        """
# Configuration

All settings come from environment variables or a `.env` file in the working
directory. Real environment variables override `.env`.

| Variable | Default | Purpose |
|---|---|---|
| `SFX_TOKEN` | – (required for API) | API access token (sent as `X-SF-Token`) |
| `SFX_REALM` | `us1` | Org realm, e.g. `eu0`, `us1`, `jp0` |
| `SFX_TIMEOUT_SECONDS` | `30` | Per-request timeout |
| `SFX_MAX_RETRIES` | `3` | Retries on 429/5xx (honours `Retry-After`) |
| `SFX_BACKOFF_FACTOR` | `0.5` | Exponential backoff factor |
| `SFX_POOL_MAXSIZE` | `10` | HTTP connection pool size |
| `SFX_CA_BUNDLE` | – | Custom CA bundle path (corporate proxy) |
| `SFX_API_BASE_URL` / `SFX_STREAM_BASE_URL` | – | Override endpoints (https only) |
| `LOG_LEVEL` | `INFO` | DEBUG, INFO, WARNING, ERROR |
| `LOG_FORMAT` | `text` | `text` or `json` |

Webhook variables: run `sfx-olly help webhook`.
""",
    ),
    "metrics": (
        "Search metrics, dimensions and MTS metadata",
        """
# Metadata

```bash
sfx-olly metrics search "name:cpu.*" --limit 20
sfx-olly metrics get cpu.utilization
sfx-olly metrics inspect example.project.size
sfx-olly -o json metrics inspect example.project.size
sfx-olly dimensions search "key:host" --limit 50
sfx-olly mts search "sf_metric:cpu.utilization AND host:web-01"
```

Query syntax is Splunk Observability search syntax (`field:value`, wildcards,
`AND`/`OR`/`NOT`). Bare terms get a default field automatically:
`metrics` -> `name:`, `dimensions` -> `key:`, `mts`/`timeseries` -> `sf_metric:`.
Max `offset + limit` is 10,000.

These commands return *metadata*. To fetch metric *values* use `sfx-olly help query`.

`metrics inspect` groups a metric's dimension keys and observed values in a tree.
It inspects up to 1000 series once; use `--limit` (max 10000) to increase that bound.
Partial inventories are labelled. The tree shows 10 values per key; JSON shows all
inspected values. Dimensions are flat literal keys: `environment` is not an alias
for `deployment.environment.name`. Use `mts search` to see valid combinations.

There is no list of never-created metrics: compare an expected-name inventory with
search results. Metadata presence does not imply recent datapoints. For availability
notifications without local polling, use a Splunk-managed detector on a known metric
or heartbeat and deliver its alerts to the webhook receiver. This is not a generic
new-metric-name notification feed.
""",
    ),
    "query": (
        "Fetch values of any metric with filters and aggregation",
        """
# Generic metric query (recommended)

Builds and runs a SignalFlow program from options, so no SignalFlow knowledge is needed.

```bash
# individual series, last 15 minutes (no default cross-series aggregation)
sfx-olly query example.bytes.total

# filter by dimensions (repeat --filter; comma = OR; '*' wildcard)
sfx-olly query example.bytes.total --filter environment=env-prod --filter 'topic=*' --agg mean

# bytes sent per topic in the last 24h (latest value only)
sfx-olly query example.bytes.total --rollup delta --agg sum --by topic \\
    --transform sum --over 1d --range 1d --resolution 1h --latest

# preview the generated SignalFlow without calling the API
sfx-olly query cpu.utilization --filter host=web-01 --agg max --by host --dry-run

# fictional example: inspect your metric for its actual dimension keys first
sfx-olly metrics inspect example.project.size
sfx-olly query example.project.size --filter environment=env-test --range 2d --latest
```

| Option | Meaning |
|---|---|
| `--filter k=v[,v]` / `--exclude k=v` | Include / exclude dimension values |
| `--rollup` | average, sum, min, max, count, delta, rate, latest, lag |
| `--agg` + `--by` | Aggregate across series, optionally grouped |
| `--transform` + `--over` | Aggregate over a time window (e.g. sum over 1d) |
| `--range` / `--resolution` | Time window / data granularity |
| `--latest` | Only the latest value per series |
| `--unit` | `raw` (default), `bytes` (auto B/KiB/MiB/GiB), `kib`, `mib`, `gib` |
| `--show-program` / `--dry-run` | Print generated SignalFlow |

Generic for queryable numeric metric series, not hardcoded to these example names.
Gauge/counter rollups must match the source and dashboard semantics. Native distributions
need specialized analytics; raw traces/logs are not implemented. `--unit` only formats
numbers and does not infer the source unit. No local polling: each query exits after
available historical results. `--latest` means latest non-null sample in the window,
not proof of current availability.
""",
    ),
    "timeseries": (
        "Fetch raw datapoints for a time window",
        """
# Time series window

```bash
sfx-olly timeseries "sf_metric:cpu.utilization AND host:web-01" --range 1h --resolution 5m
sfx-olly timeseries "sf_metric:memory.utilization" --range 15m --last 3
```

* `--range` look-back: `30s`, `15m`, `1h`, `7d`, `2w`
* `--resolution` rollup interval (min 1s)
* `--last N` points shown per series in table mode
""",
    ),
    "signalflow": (
        "Run SignalFlow analytics programs",
        """
# SignalFlow

```bash
sfx-olly signalflow "data('cpu.utilization').mean(by=['host']).publish()" --range 30m
sfx-olly signalflow --file program.flow --range 1h --resolution 1m
```

The program runs once over the window and the CLI exits when the stream ends.
Results combine each datapoint with its series metadata (dimensions).
""",
    ),
    "alerts": (
        "List detectors and incidents",
        """
# Detectors and incidents

```bash
sfx-olly detectors list --name "CPU" --limit 20
sfx-olly detectors get <detectorId>
sfx-olly incidents list                     # active only
sfx-olly incidents list --include-resolved
sfx-olly incidents get <incidentId>
```
""",
    ),
    "webhook": (
        "Receive Splunk alert webhooks and display them",
        """
# Webhook receiver

1. Generate a secret: `python -c "import secrets; print(secrets.token_urlsafe(32))"`
2. Put it in `.env` as `WEBHOOK_SHARED_SECRET` (same value in Splunk).
3. Start: `sfx-olly webhook serve`
4. Test locally (signed sample): `sfx-olly webhook send-test`
5. In Splunk: Data Management → Webhook integration → URL = your public
   **HTTPS** URL + `WEBHOOK_PATH`, Shared secret = same value. Add it as a
   detector alert recipient.
6. Re-render saved alerts: `sfx-olly webhook render alerts.jsonl`

| Variable | Default | Purpose |
|---|---|---|
| `WEBHOOK_HOST` | `127.0.0.1` | Bind address (`0.0.0.0` in containers) |
| `WEBHOOK_PORT` | `8080` | Port |
| `WEBHOOK_PATH` | `/webhooks/splunk` | Endpoint path |
| `WEBHOOK_WORKERS` | `1` | Uvicorn worker processes |
| `WEBHOOK_SHARED_SECRET` | – | HMAC-SHA256 secret (required by default) |
| `WEBHOOK_REQUIRE_SIGNATURE` | `true` | Refuse to start without a secret |
| `WEBHOOK_MAX_BODY_BYTES` | `262144` | Reject larger payloads (413) |
| `WEBHOOK_ALLOWED_CIDRS` | – | Comma-separated source CIDR allowlist |
| `WEBHOOK_TRUST_PROXY_HEADERS` | `false` | Use X-Forwarded-For from proxy |
| `WEBHOOK_FORWARDED_ALLOW_IPS` | `127.0.0.1` | Proxies trusted for those headers |
| `WEBHOOK_DEDUPE_TTL_SECONDS` | `300` | Drop repeated deliveries |
| `WEBHOOK_CONSOLE_OUTPUT` | `true` | Pretty-print alerts to stdout |
| `WEBHOOK_OUTPUT_FILE` | – | Also append alerts as JSON lines |
| `WEBHOOK_SSL_CERTFILE` / `WEBHOOK_SSL_KEYFILE` | – | Serve TLS directly |

Endpoints: `POST WEBHOOK_PATH`, `GET /healthz`.
""",
    ),
    "security": (
        "Security controls built into the toolkit",
        """
# Security

* Secrets only from env/.env, held as `SecretStr`, redacted from logs and errors.
* HTTPS enforced, TLS verification on, redirects disabled (token never leaks).
* Realm and IDs validated; path parameters URL-encoded; input sizes bounded.
* Timeouts, bounded retries with backoff and `Retry-After` support.
* Webhook: HMAC-SHA256 signature (constant-time compare), body size limit,
  content-type check, optional CIDR allowlist, replay de-duplication,
  no OpenAPI/docs endpoints, no payload echo, terminal-safe rendering,
  JSONL output created with 0600 permissions.
* Never commit `.env`; use a secret manager (e.g. Azure Key Vault) in production.
""",
    ),
    "library": (
        "Use the package from your own Python code",
        """
# Library usage

```python
from sfx_olly import SplunkOllyClient
from sfx_olly.api import MetricQuery
from sfx_olly.utils import time_range

with SplunkOllyClient() as client:            # reads SFX_* settings
    for m in client.metadata.iter_metrics("name:cpu.*", max_items=500):
        print(m["name"])

    start, end = time_range("1h")
    points = client.signalflow.query(
        MetricQuery("example.bytes.total",
                    filters={"environment": ["env-prod"]},
                    aggregation="sum", group_by=["topic"]),
        start, end,
    )
```

Custom webhook sink:

```python
from sfx_olly.config import get_webhook_settings
from sfx_olly.webhook.app import create_app

class SlackHandler:
    def handle(self, alert):  # alert: AlertPayload
        ...

app = create_app(get_webhook_settings(), handlers=[SlackHandler()])
```
""",
    ),
}


def topic_names() -> list[str]:
    return list(TOPICS)


def get_topic(name: str) -> str:
    key = name.strip().lower()
    if key not in TOPICS:
        suggestion = difflib.get_close_matches(key, TOPICS, n=1)
        hint = f" Did you mean '{suggestion[0]}'?" if suggestion else ""
        raise ValueError(f"Unknown help topic '{name}'.{hint} Available: {', '.join(TOPICS)}")
    return TOPICS[key][1]


def show(topic: str | None = None, console: Console | None = None) -> None:
    console = console or Console()
    if topic:
        console.print(Markdown(get_topic(topic)))
        return
    table = Table(title="sfx-olly help topics", show_header=True, header_style="bold")
    table.add_column("Topic", style="bold cyan")
    table.add_column("Description")
    for name, (summary, _) in TOPICS.items():
        table.add_row(name, summary)
    console.print(table)
    console.print("Run [bold]sfx-olly help <topic>[/] or [bold]sfx-olly <command> -h[/].")
