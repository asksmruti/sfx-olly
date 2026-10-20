# Command Guide

Start here if metrics, dimensions, SignalFlow, or the command options are unfamiliar.
Examples use fictional project-size metrics, but the commands work with other queryable numeric metrics.
Names such as `example.project.size`, `example.bytes.total`, `project-demo`, and
`env-test` are placeholders. Replace them with your own discovered metric/dimension
values to return data. No organization-specific names or operational results are required.
All numbers in the teaching tables are illustrative, not measurements from your system.

## Contents

1. [Start with these commands](#start-with-these-commands)
2. [Metric, dimension, series, and datapoint](#metric-dimension-series-and-datapoint)
3. [Read a command](#read-a-command)
4. [Discover names and dimensions](#discover-names-and-dimensions)
5. [Filters: choose the right series](#filters-choose-the-right-series)
6. [Range: how far back to look](#range-how-far-back-to-look)
7. [Resolution: the size of a time bucket](#resolution-the-size-of-a-time-bucket)
8. [Rollup: samples inside one bucket](#rollup-samples-inside-one-bucket)
9. [Aggregation: combine different series](#aggregation-combine-different-series)
10. [Grouping: one answer per project or host](#grouping-one-answer-per-project-or-host)
11. [Transform: calculate over time](#transform-calculate-over-time)
12. [The order of operations](#the-order-of-operations)
13. [Gauges, counters, and choosing a calculation](#gauges-counters-and-choosing-a-calculation)
14. [Units, timestamps, and latest values](#units-timestamps-and-latest-values)
15. [Your project-size query, step by step](#your-project-size-query-step-by-step)
16. [Recipes by question](#recipes-by-question)
17. [Every query option](#every-query-option)
18. [Other commands](#other-commands)
19. [Match a dashboard and troubleshoot](#match-a-dashboard-and-troubleshoot)
20. [Common mistakes](#common-mistakes)

## Start with these commands

Complete the [installation and configuration](../README.md#installation) first.
Run commands from the project directory if your settings are in its `.env` file.
Never paste your API token or webhook secret into a support message.

```bash
# Find metric names using a fictional example prefix.
sfx-olly metrics search 'example.*'

# Discover which dimension keys and values exist for this metric.
sfx-olly metrics inspect example.project.size

# Read one project's individual series, without aggregation.
sfx-olly query example.project.size \
  --filter environment=env-test \
  --filter project.name=project-demo \
  --range 1h --resolution 1m --unit kib
```

The last command assumes the metric's source values are bytes. It returns historical
values, not a live subscription. If you only need the latest non-null value per series
within that hour, append `--latest`. If the command returns no data, discover the
dimensions first and then try a wider range; do not add aggregation to fix an empty filter.

If `sfx-olly` is not found, replace it with `python -m sfx_olly`, using the Python
environment in which the project dependencies are installed.

## Metric, dimension, series, and datapoint

| Term | Plain meaning | Example |
| --- | --- | --- |
| Metric | The name of something being measured. | `example.project.size` |
| Dimension key | A label that identifies which thing was measured. | `project.name`, `environment`, `host.name` |
| Dimension value | The value of one of those labels. | `project-demo`, `env-test` |
| Metric time series (MTS) | One metric plus a particular dimension set. | Project A on host 1 in test |
| Datapoint | A value attached to a timestamp in a series. | At 10:00 UTC, size was 102400 bytes |
| Metadata | Information describing metrics or series, not their numeric history. | Metric type, description, dimension keys |

```text
Metric: example.project.size
  Series 1: environment=test, project.name=A, host.name=host-1
    10:00 -> 100 KiB
    10:01 -> 120 KiB
  Series 2: environment=test, project.name=A, host.name=host-2
    10:00 -> 200 KiB
    10:01 -> 220 KiB
  Series 3: environment=test, project.name=B, host.name=host-1
    10:00 ->  50 KiB
    10:01 ->  60 KiB
```

One project can have several series because hosts or other dimensions differ.
Filtering by project does not necessarily select just one series.

Dimensions are a **flat map**, not nested folders. `deployment.environment.name`
is a literal key; it is not the same key as `environment`, `env`, or `clusterName`.
Names and values should be copied exactly from discovery results, including case.

The inspection tree groups observed values for readability. It does not guarantee
that every displayed project exists with every displayed host or environment.

## Read a command

```bash
sfx-olly query example.project.size --filter environment=env-test --range 1h
```

Read it as: "Fetch values of `example.project.size`, keep series labelled
`environment=env-test`, and look back one hour from now."

| Part | What it does |
| --- | --- |
| `sfx-olly` | Starts this tool. |
| `query` | Selects the metric-values command. |
| `example.project.size` | Supplies the required metric name. |
| `--filter` | Introduces a dimension condition. |
| `--range` | Introduces the historical look-back period. |

In multiline examples, a final backslash continues the same shell command on the next
line. Do not put spaces after that backslash. You can also enter the whole command
on one line, without the backslashes.

## Discover names and dimensions

```bash
# First page of indexed metric names, not datapoint values.
sfx-olly metrics search
sfx-olly metrics search 'example.*' --limit 100

# Metric metadata, including type when supplied by Splunk.
sfx-olly metrics get example.project.size

# A readable dimension tree for this metric.
sfx-olly metrics inspect example.project.size

# All observed values from the inspected series, in JSON.
sfx-olly -o json metrics inspect example.project.size --limit 2000

# Dimension combinations on individual series, not independent value lists.
sfx-olly mts search 'sf_metric:example.project.size AND environment:env-test'

# Global dimension search: may include dimensions from other metrics.
sfx-olly dimensions search 'key:host.name' --limit 50
```

`inspect` examines at most 1000 series by default, with a maximum of 10000.
It labels partial inventories. The tree displays at most 10 values per key;
JSON includes all values found in the inspected subset.

Search commands return 50 results by default. `--limit 50 --offset 50` requests
the next page after the first 50 results. Keep offset plus limit at or below 10000.
`inspect` has `--limit` but no `--offset` option.

There are two different syntaxes:

| Command | Syntax | Example |
| --- | --- | --- |
| `metrics search` | Metadata search expression | `'name:example.*'` |
| `mts search` / `timeseries` | Series search expression | `'sf_metric:example.project.size AND environment:env-test'` |
| `query --filter` | Dimension key equals value | `--filter environment=env-test` |

Bare metric names in search commands get a default field automatically. Use quoted
full search expressions for more complex conditions. A metric that was never ingested
cannot be discovered by listing "unavailable" names; compare with an expected inventory.
Indexed metadata can remain even when there are no recent samples.

## Filters: choose the right series

Filters select input series before calculations. They do not change numeric values.

```bash
# Both conditions must match: environment AND project.
sfx-olly query example.project.size \
  --filter environment=env-test \
  --filter project.name=project-demo

# Either environment may match: test OR production.
sfx-olly query example.project.size \
  --filter environment=env-test,env-prod

# Wildcard value: quote it to prevent shell wildcard expansion.
sfx-olly query example.project.size --filter 'project.name=METRICS_*'

# Keep test but exclude one project.
sfx-olly query example.project.size \
  --filter environment=env-test \
  --exclude project.name=project-demo
```

Different included keys are combined with AND. Values for the same key are combined
with OR, including when that key is repeated in multiple `--filter` options.
`--exclude` removes matches; comma-separated values exclude any matching value.
The convenience parser uses commas as separators, so a literal comma inside a
dimension value needs custom SignalFlow rather than this option format.
Quotes, backslashes, and control characters inside filter values are rejected by
the builder. Shell quoting does not remove those builder restrictions.

## Range: how far back to look

`--range` answers: **which historical period do I want?**

The default is `15m`. `--range 1h` means from one hour ago until now, not "return
one average for the hour" and not "keep running for an hour".

| Value | Look back |
| --- | --- |
| `30s` | 30 seconds |
| `15m` | 15 minutes |
| `1h` | 1 hour |
| `2d` | 2 days |
| `1w` | 1 week |

Durations use positive whole numbers with `s`, `m`, `h`, `d`, or `w`. There is no
month unit; `m` always means minutes. Use `90m`, not `1.5h`. The CLI currently has
no absolute `--start` / `--end` options. Separate runs have slightly different end
times because each ends at its own current time.

## Resolution: the size of a time bucket

`--resolution` answers: **how finely should time be represented?**

The default is `1m`. Roughly speaking, `--range 1h --resolution 1m` asks for
minute-sized buckets over an hour. It is not a request to wait a minute between
HTTP calls. This tool does not poll for values.

| Example | Approximate buckets per output series |
| --- | --- |
| `--range 1h --resolution 1m` | 60 |
| `--range 1h --resolution 5m` | 12 |
| `--range 1d --resolution 1h` | 24 |

These are intuition, not guaranteed row counts. Splunk can adjust the actual
resolution based on retention and availability; boundary alignment, sparse samples,
and calculations also affect output. A one-minute request cannot create one-minute
data from a source that reports hourly. The supported requested interval is 1 second
through 1 day, inclusive.

Start with a resolution much smaller than your range and match the dashboard when
comparing values. With `--range 1h --resolution 16h`, one requested bucket is larger
than the entire requested period. Coarse, aligned buckets can be labelled outside
the selected hour and are not directly comparable to a fine-resolution chart hover
value. The CLI currently allows this combination; it does not automatically correct it.

## Rollup: samples inside one bucket

`--rollup` chooses how raw observations for **each individual series** are reduced
to values at the requested resolution. If omitted, Splunk chooses its default
based on the metric type; this CLI does not force `average` or `latest`.

Suppose a size gauge reports 100, 120, and 140 KiB inside one five-minute bucket:

| Rollup | Result for this teaching example | Interpretation |
| --- | --- | --- |
| `average` | 120 KiB | Typical sampled size in the bucket. |
| `min` | 100 KiB | Smallest sampled size. |
| `max` | 140 KiB | Largest sampled size. |
| `latest` | 140 KiB | Last sample in the bucket. |
| `sum` | 360 KiB | Sum of the readings, usually not meaningful as current project size. |
| `count` | 3 | Number of samples, not number of hosts or projects. |

The table assumes all three samples are available and applicable to that rollup.
Not every rollup is valid or meaningful for every source type. The CLI accepts these
names, but Splunk ultimately decides whether a request is supported:

| Rollup | Use or caution |
| --- | --- |
| `average`, `min`, `max`, `latest` | Common gauge comparisons; choose the same one as the chart. |
| `sum`, `count` | Sum observations or count observations inside buckets; output meaning changes. |
| `delta` | Counter change/increment semantics; appropriate to supported counter data, not a generic way to subtract gauge endpoints. |
| `rate` | Counter activity per unit time, normally per second; verify source and API semantics. |
| `lag` | Specialized reporting-lag information, not the original metric magnitude; avoid for ordinary size comparisons. |

```bash
# Largest observed project size in each requested five-minute bucket.
sfx-olly query example.project.size \
  --filter environment=env-test \
  --filter project.name=project-demo \
  --range 1h --resolution 5m --rollup max --unit kib
```

Do not choose `sum` just because a metric has "total" in its name. Inspect its type
and the producer's definition first.

## Aggregation: combine different series

`--agg` answers: **at each output timestamp, how should different matching series
be combined?** It does not add together all timestamps in the requested range.

Without `--agg`, each matching series is returned separately.

Suppose three independent inputs have values 100, 200, and 300 at the same timestamp:

| `--agg` | Result | Meaning |
| --- | --- | --- |
| `sum` | 600 | Add the three inputs. |
| `mean` | 200 | Arithmetic average of the inputs. |
| `min` | 100 | Smallest input. |
| `max` | 300 | Largest input. |
| `count` | 3 | Number of contributing series values, not their sum. |
| `median` | 200 | Middle input when sorted. |
| `stddev` | Spread, in the input's units | Standard deviation; not a sum or typical value. |
| `variance` | Spread, in squared input units | Variance; not a size in bytes or KiB. |

This example assumes three present inputs. Missing values, extrapolation in custom
programs, and backend function rules can change which inputs contribute. Do not use
these counts as a guaranteed inventory of configured hosts.

```bash
# Largest matching project-size series at each output timestamp.
sfx-olly query example.project.size \
  --filter environment=env-test \
  --agg max --range 1h --resolution 1m --unit kib

# Number of contributing series at each timestamp; leave the unit raw.
sfx-olly query example.project.size \
  --filter environment=env-test \
  --agg count --range 1h --resolution 1m
```

Aggregation is a business decision, not just a display preference. Summing two hosts
that report the same shared project size would double-count that size. Summing
distinct independent contributions may be correct. Only the metric producer can
establish whether the inputs are additive. Likewise, averaging percentages from
unequal-capacity hosts is not necessarily a capacity-weighted utilization.

With exactly one contributing series, sum/mean/min/max have the same value at
that timestamp. `count` would still produce a count, not the original value.

## Grouping: one answer per project or host

`--by` divides series into groups before applying `--agg`. It is not another filter.
With no grouping, the aggregation combines all matching series into one result
stream. With grouping, it produces a stream for each observed group.

Using the three series from the earlier teaching example, at 10:00:

| Options | Result |
| --- | --- |
| No `--agg` | A/host-1=100, A/host-2=200, B/host-1=50 |
| `--agg sum` | One combined result: 350 |
| `--agg sum --by project.name` | A=300, B=50 |
| `--agg sum --by host.name` | host-1=150, host-2=200 |
| `--agg sum --by project.name --by host.name` | Separate results for each observed project/host pair |

```bash
# One total per project, if the underlying series are genuinely additive.
sfx-olly query example.project.size \
  --filter environment=env-test \
  --agg sum --by project.name --range 1h --resolution 1m --unit kib
```

Use `--by` once per key: `--by project.name --by host.name`. A comma-separated
`--by project.name,host.name` is not this CLI's grouping syntax.
`--by` requires `--agg`; the builder rejects grouping on its own.
Discover the key first and check series where the grouping dimension is missing.
Grouping can remove the identity of individual input series, so inspect unaggregated
results when you need to understand exactly which hosts contributed.

## Transform: calculate over time

`--transform` plus `--over` answers: **for each output series, how should values
over a moving historical window be combined?**

The window is evaluated at each output timestamp. It is not automatically one final
answer for the entire `--range` and is not a calendar-day report.

```bash
# For each input series, show a moving one-hour average project size.
sfx-olly query example.project.size \
  --filter environment=env-test \
  --range 6h --resolution 5m --transform mean --over 1h --unit kib

# First choose the largest input at each timestamp, then its moving one-hour max.
sfx-olly query example.project.size \
  --filter environment=env-test \
  --agg max --range 6h --resolution 5m \
  --transform max --over 1h --unit kib
```

For an illustrative sequence 100, 120, 140, a moving sum over a window containing
all three values would be 360, while its moving mean would be 120. Summing size-gauge
readings normally does not mean "current size" or "bytes transferred".

Both options must be supplied together. The allowed function names are the same as
the aggregation choices, but actual support and statistical/window behavior depend
on SignalFlow. The window format here is a positive integer of at most five digits
followed by lowercase `s`, `m`, `h`, `d`, or `w`. Use custom SignalFlow for calculations
that need different ordering, calendar windows, weighting, or unsupported functions.
Splunk may need history before the requested start to initialize a moving calculation;
missing history can affect early outputs.

## The order of operations

```text
Choose metric and matching dimension sets
  -> roll up each input series to the requested resolution
  -> aggregate across series, optionally grouped by dimension
  -> transform each resulting series over a moving time window
  -> publish results
  -> optionally display only the latest non-null point per output series
  -> format numbers for display
```

`--range` determines the historical output period. `--resolution` controls the
requested granularity; it is not a fourth aggregation function.

These operations are not interchangeable. For example, "maximum host value over
time" and "sum of each host's maximum" can differ because the hosts may peak at
different timestamps. The builder's order is fixed. Inspect it without API access:

```bash
sfx-olly query example.project.size \
  --filter environment=env-test \
  --rollup max --agg sum --by project.name \
  --transform mean --over 1h --dry-run
```

The generated program is:

```python
data('example.project.size', filter=filter('environment', 'env-test'), rollup='max').sum(by=['project.name']).mean(over='1h').publish(label='A')
```

This is SignalFlow syntax, not a Python script to run with the Python interpreter.
It means: within each bucket take each input's maximum; sum those values per project;
then compute a moving one-hour mean for each resulting project stream.

## Gauges, counters, and choosing a calculation

| Measurement | Often represented as | Starting approach |
| --- | --- | --- |
| Current project size, temperature, utilization | Gauge: value can rise or fall. | Start without aggregation; match chart average/max/latest rollup. |
| Events recorded per reporting interval | Counter: interval increments. | Check the metric definition and supported rollup; don't differentiate increments again. |
| Lifetime bytes or requests | Cumulative counter: generally rises, but can reset. | Use a backend-supported change/rate calculation appropriate to the source. |
| Histogram buckets or summaries | Several numeric metrics or specialized distributions. | Query numeric series carefully; do not assume bucket totals are percentiles. |

Metric names alone are insufficient. For these examples, assume `example.project.size`
is a **GAUGE** reporting bytes. Check your real metric's type and confirm its unit
from the collector/application before applying a byte display unit. Metadata may not
specify a unit.

For cumulative readings 1000, 1100, 1250, adding them gives 3350, not the increase.
The simple endpoint increase is 250 if no reset occurred. Real counter queries also
need to handle resets, sample timing, and the producer's metric conventions.

| Your question | Consider |
| --- | --- |
| What did this one series report? | No `--agg` or `--transform` initially. |
| What is the largest independent input at each timestamp? | `--agg max` |
| What is the total of additive inputs per project? | `--agg sum --by project.name` |
| What is the typical value across equally weighted input series? | `--agg mean` |
| What is the average of each series over the previous hour? | `--transform mean --over 1h` |
| What was the largest raw reading within each time bucket? | `--rollup max` |
| What was the last available returned value per series? | `--latest`, a display selection rather than a calculation. |

## Units, timestamps, and latest values

`--unit` affects table display only. It does not change the query, guess the metric's
source unit, change timestamps, or make results equivalent to a dashboard calculation.

| Option | Behavior, assuming the source is bytes |
| --- | --- |
| `--unit raw` | Print the numeric API value without byte conversion; default. |
| `--unit kib` | Divide by 1024 and display KiB. |
| `--unit mib` | Divide by 1048576 and display MiB. |
| `--unit gib` | Divide by 1073741824 and display GiB. |
| `--unit bytes` | Choose B, KiB, MiB, or GiB automatically based on magnitude. |

For example, 114688 bytes = 112 KiB. Decimal kB uses a factor of 1000, not 1024;
that difference is small and cannot explain a difference like 310 versus 112.
If the source already reports KiB, dividing it by 1024 again would be incorrect.
Use raw units for counts, percentages, and variance unless you explicitly know the
intended conversion. JSON remains raw even when a display unit is requested.

Output timestamps are UTC. Bucket timestamps represent a computation interval,
not necessarily the exact arrival time of a raw sample. Check the dashboard timezone.

`--latest` selects the last non-null returned point for each output series. It does
not select the maximum, fill gaps, or keep only one series overall. With a two-day
range it can show a sample from yesterday. It does not prove the metric is reporting now.
An actual zero value is retained and is not considered missing.

## Your project-size query, step by step

Start without calculations, then add only the ones that answer your question.

### Step 1: Check the project and environment

```bash
sfx-olly mts search 'sf_metric:example.project.size AND environment:env-test AND project.name:project-demo'
```

Look at how many series match and their full dimension sets. One project can have
multiple hosts. Do not assume one series just because the filter names one project.

### Step 2: Inspect historical values

```bash
sfx-olly query example.project.size \
  --filter environment=env-test \
  --filter project.name=project-demo \
  --range 1h --resolution 1m --unit kib
```

This does not specify a rollup, so Splunk chooses the metric's default. Compare
actual timestamps and values, not just the last number on the screen.

### Step 3: Reduce the display, not the calculation

```bash
sfx-olly query example.project.size \
  --filter environment=env-test \
  --filter project.name=project-demo \
  --range 1h --resolution 1m --unit kib --latest
```

### Step 4: Add a calculation only if needed

If distinct additive inputs exist and the question is "total per project at each
timestamp", add `--agg sum --by project.name`. If inputs are duplicate reports of the
same shared size, sum is not correct. If you need no cross-series combination, leave
both options off. Changing aggregation to force a match with the UI hides the cause.

### Step 5: Understand your original command

```text
--filter environment=env-test       Select the test environment.
--filter project.name=project-demo
                                         Also select this exact project.
--range 1h                               Ask for the preceding hour.
--unit kib                               Display bytes divided by 1024.
--agg sum --by project.name                  Sum matching inputs per project at each timestamp.
--resolution 16h                         Ask for buckets much larger than that hour.
```

For illustration, a coarse bucket might show 300 KiB while a finer bucket shows
120 KiB because they summarize different samples. Those teaching numbers are not
results from your account. With one contributing series, sum and no aggregation
match at the same timestamp; different bucket sizes can still produce different
values. Compare the dashboard's exact timestamp, rollup, and resolution first.

## Recipes by question

### What are all the matching projects reporting individually?

```bash
sfx-olly query example.project.size --filter environment=env-test \
  --range 2d --resolution 5m --unit kib --latest
```

This can still return multiple series for the same project. It does not merge hosts.

### What is the peak reported value per project at each timestamp?

```bash
sfx-olly query example.project.size --filter environment=env-test \
  --agg max --by project.name --range 1d --resolution 5m --unit kib
```

This takes the maximum across input series per project at each bucket. It is not
one maximum over the entire day. `--resolution 5m` may itself hide within-bucket
peaks if the source/default rollup averages; add `--rollup max` only if that is the
supported calculation you want.

### What is the byte rate per topic for a supported counter?

```bash
sfx-olly query example.bytes.total \
  --filter environment=env-prod \
  --rollup rate --agg sum --by topic --range 1h --resolution 1m
```

Use this only after confirming the source is a counter for which Splunk's `rate`
rollup has the intended semantics. A name ending in `total` is not sufficient proof.
If the input counts bytes and the rate is per second, the result means bytes per
second, not total bytes over the hour. It intentionally uses raw display units.
Verify that producers are distinct contributions before summing them; duplicate
reporters can double-count rates too. Counter resets and reporting intervals matter.

### What is the moving peak per project over the previous hour?

```bash
sfx-olly query example.project.size --filter environment=env-test \
  --rollup max --agg max --by project.name \
  --transform max --over 1h --range 6h --resolution 5m --unit kib
```

This intentionally uses maximum at all three calculation stages. Each output point
summarizes its preceding hour; there are still several output timestamps.

### How do I export results as JSON?

```bash
sfx-olly -o json query example.project.size \
  --filter environment=env-test --range 1h --latest
```

`-o json` is a global option and belongs before `query`. The JSON contains numeric
values, timestamps in milliseconds, series IDs, and properties. Do not combine
`--show-program` with JSON when you need stdout to contain only JSON: that option
also prints the program to stdout. Use a separate `--dry-run` command instead.

### How do I inspect the request without querying Splunk?

```bash
sfx-olly query example.project.size --filter environment=env-test \
  --agg max --by project.name --dry-run
```

`--dry-run` prints SignalFlow and makes no API call. It validates the builder inputs,
but does not prove the metric exists or that Splunk supports the requested calculation.
Range/resolution are request parameters, not part of the printed program; the dry-run
path does not validate those parameters. For endpoint and request timing diagnostics:

```bash
sfx-olly -v query example.project.size --filter environment=env-test \
  --range 1h --resolution 1m --latest
```

Verbose mode makes a real request and logs diagnostics to stderr. The token is
redacted, but query text and business dimension values can still be sensitive.

## Every query option

| Option | Default | What to remember |
| --- | --- | --- |
| Metric name | Required | Numeric metric to fetch; wildcard patterns are allowed. |
| `--filter KEY=V[,V]` | None | Keep matching dimensions; repeat for more keys. |
| `--exclude KEY=V[,V]` | None | Remove matching dimensions. |
| `--range DURATION` | `15m` | Historical output period ending now. |
| `--resolution DURATION` | `1m` | Requested time-bucket interval, 1s through 1d. |
| `--rollup NAME` | Backend default | Per-series treatment within a bucket. |
| `--agg NAME` | No aggregation | Cross-series calculation at each timestamp. |
| `--by DIMENSION` | No grouping | Requires `--agg`; repeat once per grouping key. |
| `--transform NAME` | No transform | Moving time calculation; requires `--over`. |
| `--over DURATION` | None | Moving window; requires `--transform`. |
| `--latest` | Off | Display latest non-null point per output series in the window. |
| `--unit raw/bytes/kib/mib/gib` | `raw` | Display formatting only; JSON stays raw. |
| `--label NAME` | `A` | SignalFlow output label; does not filter input dimensions. |
| `--show-program` | Off | Print generated SignalFlow, then execute it. |
| `--dry-run` | Off | Print generated SignalFlow and exit without an API call. |
| `-h`, `--help` | Off | Show this command's option summary. |

Aggregation and transform choices: `mean`, `sum`, `min`, `max`, `count`, `median`,
`stddev`, `variance`. Rollup choices: `average`, `sum`, `min`, `max`, `count`, `delta`,
`rate`, `latest`, `lag`. These are accepted builder names, not a guarantee of every
function/source/window combination at the API.

The naming difference is intentional: the rollup choice is `average`, while the
cross-series aggregation and moving-transform choice is `mean`. For example,
`--rollup average --agg mean` first averages samples per input bucket and then
averages those resulting values across input series.

Labels allow letters, digits, underscores, and hyphens, up to 64 characters. For
dimension names, use those found by inspection; the convenience builder permits
letters, digits, underscores, dots, colons, slashes, and hyphens (up to 128 characters).
Other valid source names/values may require custom SignalFlow if this builder rejects them.

Global options go before the command:

| Option | Meaning |
| --- | --- |
| `-o table` | Default readable tables, or a tree for metric inspection. |
| `-o json` | Machine-readable results; `query` values stay raw. |
| `-v`, `--verbose` | Log requests and timings to stderr; not live polling. |
| `--version` | Show the installed toolkit version. |
| `--help` | Show the command list. |

`metrics get`, `detectors get`, and `incidents get` always print JSON.
Global output selection does not turn the webhook
receiver into a raw-JSON console stream; use its JSONL output file for saved payloads.

## Other commands

### Discovery option reference

| Command | Inputs and options | Result |
| --- | --- | --- |
| `metrics search` | Optional search text (default `*`); `--limit` (50), `--offset` (0). | Indexed metric metadata, not samples. |
| `metrics get` | Required metric name. | Full metric metadata as JSON. |
| `metrics inspect` | Required metric name; `--limit` (1000). | Dimension tree or JSON; reports partial inventories. |
| `dimensions search` | Required search text; `--limit` (50), `--offset` (0). | Global dimension metadata, not scoped to one metric. |
| `mts search` | Required search text; `--limit` (50), `--offset` (0). | Individual matching series and their dimension combinations. |

```bash
# Request the next 50 results, skipping the first page.
sfx-olly metrics search 'example.*' --limit 50 --offset 50
```

### Run SignalFlow copied from the UI

```bash
sfx-olly signalflow "data('cpu.utilization').mean(by=['host']).publish()" \
  --range 1h --resolution 1m
sfx-olly signalflow --file chart.flow --range 1h --resolution 1m --unit kib
```

The file example assumes your copied program exists at that path. There is no
reverse-conversion requirement: the tool sends the program directly to SignalFlow.
Use either positional program text or `--file`, not both. File size is bounded at
50000 bytes; the program text also has a length limit.

The program must publish the desired output. Resolve UI-specific arguments and
dashboard variables first; this CLI has no `--program-args` option. Keep only the
intended enabled outputs. Custom SignalFlow may perform its own scaling, so check
that you are not converting bytes to KiB twice. Supported display options are
`--latest` and `--unit`; builder options such as `--agg` belong inside the custom
program, not after `signalflow` on the command line.

### Raw time-series window

```bash
sfx-olly timeseries 'sf_metric:example.project.size AND environment:env-test' \
  --range 1h --resolution 5m --last 3
```

`timeseries` uses a different raw-data API rather than generating SignalFlow.
`--last 3` shows the last three returned points per series in table output; it does
not reduce the fetched window. JSON still contains the complete response data.
Its default `--last` is 5. This command has no `--unit`, `--agg`, or `--latest` option.
Use `query` for dimension-labelled analytics and unit formatting.

### Detectors and incidents

Both plural and singular command names work: `incidents` / `incident` and
`detectors` / `detector`. They are aliases with identical list/get behavior.

```bash
sfx-olly detectors list --name CPU --limit 20
sfx-olly detectors list --tag production --limit 20
sfx-olly detectors get YOUR_DETECTOR_ID
sfx-olly incidents list
sfx-olly incidents list --include-resolved --limit 100
sfx-olly incidents get YOUR_INCIDENT_ID
sfx-olly incident list
sfx-olly detector list --limit 20
```

A detector is an alerting rule configuration. An incident is an occurrence of that
rule firing. These commands retrieve metadata; they do not create a detector or
acknowledge an incident. Replace `YOUR_DETECTOR_ID` / `YOUR_INCIDENT_ID` with an ID
returned by the respective list command; an ID is not the display name.

| Option or input | Applies to | Meaning |
| --- | --- | --- |
| `--name TEXT` | `detectors list` | Name substring filter. |
| `--tag TAG` | `detectors list` | Detector tag filter. |
| `--include-resolved` | `incidents list` | Also request resolved incidents; default listing is active-only. |
| `--limit N` | Both list commands | Max results for this request; default 50. |
| `--offset N` | Both list commands | Number of results to skip; default 0. |
| Required ID | Both get commands | Retrieve one detector/incident, printed as JSON. |

### Webhook receiver and tests

```bash
sfx-olly webhook serve
```

Run the following in another terminal while the receiver stays running:

```bash
sfx-olly webhook send-test
sfx-olly webhook send-test --state ok
```

Unlike historical queries, `webhook serve` is a long-running HTTP listener. It
receives notifications, rather than polling Splunk. `send-test` creates a synthetic
CPU critical alert, not a detector or a real incident in your Splunk organization.
The two commands do not automatically subscribe you to every detector.

Configure the shared secret, public HTTPS URL, and detector recipient using the
[webhook setup](reference.md#webhook-receiver) and
[local/tunnel/Splunk test sequence](reference.md#end-to-end-webhook-test).
Use `webhook render` to display saved JSON/JSONL alerts. Configure
`WEBHOOK_OUTPUT_FILE` to preserve payloads; console output is a formatted summary.

| Option or input | Applies to | Meaning |
| --- | --- | --- |
| `--url URL` | `webhook send-test` | Override the derived local URL, for example to test through ngrok. Include the webhook path. |
| `--file PATH` | `webhook send-test` | Send your existing JSON payload file instead of generating the sample. |
| `--state STATE` | `webhook send-test` | Sample state: `anomalous` (default), `ok`, `manually resolved`, or `stopped`. Quote values containing spaces. |
| `--insecure` | `webhook send-test` | Skip TLS certificate verification for isolated self-signed local tests only. Do not use for ngrok or production. |
| Required file path | `webhook render` | Read an existing `.json` or `.jsonl` alert file and display it. No API query. |
| `WEBHOOK_*` settings | `webhook serve` | Configure secret, host, port, output, and security through env/.env, not `--port` or `--secret` CLI options. |

`--state` controls the generated sample; it does not rewrite a supplied `--file`
payload. Both file-based operations limit input file size to 50 MiB.

```bash
sfx-olly webhook send-test --state 'manually resolved'
sfx-olly webhook send-test --file my-payload.json
sfx-olly webhook render ./data/alerts.jsonl
```

The last two examples require those files to exist; the JSONL file is only created
when file output is configured and notifications are received.

### Offline help

```bash
sfx-olly help
sfx-olly help query
sfx-olly help signalflow
sfx-olly query --help
sfx-olly metrics inspect --help
```

Help and dry-run work without API credentials. Help text lists options; this guide
explains which question each option answers and how the operations interact.

## Match a dashboard and troubleshoot

Use this comparison sequence rather than changing several options at once:

1. Confirm the same organization/realm and API permissions.
2. Copy the metric and filter keys exactly; inspect series and dimension combinations.
3. Match the chart's time range, UTC timestamps, and actual resolution. A chart hover
   is one timestamp, not the latest sample from a later CLI execution.
4. Compare the chart's rollup. An average bucket can differ from its maximum or last sample.
5. Compare cross-series aggregation and grouping. Check for duplicate reporters.
6. Compare time transforms, formulas, weighting, extrapolation, and unit conversion.
7. Run the chart's actual SignalFlow if the simple builder cannot express its logic.
8. Compare raw values before formatting; then apply the same display unit.

No data does not mean zero, and it does not prove the metric never existed. Filters,
range, sparse reporting, token visibility, and retained metadata are separate checks.
Avoid automatic fill/extrapolation just to make a result resemble the UI.

| Symptom | First check |
| --- | --- |
| Empty result | Remove one filter at a time; inspect dimensions; widen range if appropriate. |
| Number larger than UI | Bucket size/rollup, summed duplicate series, transformations, units. |
| Multiple rows for one project | Other dimensions identify distinct series or multiple timestamps remain. |
| One old row with `--latest` | It is the last available non-null point in the range, not necessarily current. |
| `--by` error | Supply `--agg` and repeat `--by` separately for each key. |
| Transform/window error | Supply both `--transform` and `--over`. |
| Unrecognized global option position | Put `-o json` / `-v` before `query` or another top-level command. |
| HTTP 401/403 | Check token API permissions and correct organization; do not share tokens. |
| Webhook 404/401 | Check URL path / shared-secret signature respectively; see webhook tests. |

## Common mistakes

| Mistake | Better approach |
| --- | --- |
| Adding flags without deciding what the result should mean. | Write the question first, then add one operation at a time. |
| Using `--range 1h --resolution 16h` to compare a chart hover. | Match chart resolution and keep buckets sensibly smaller than the range. |
| Thinking `--agg sum` gives the total over the range. | It sums series at each timestamp; time calculations are a different stage. |
| Using `--rollup sum` to find current project size. | A size is usually a gauge; inspect readings and match the chart's rollup. |
| Treating a moving sum of gauge readings as transferred bytes. | Use the appropriate transfer/counter metric and supported counter semantics. |
| Thinking `--latest` means raw source sample or maximum. | It selects the latest non-null returned output point after all calculations. |
| Treating `environment` as an alias of `deployment.environment.name`. | Use the literal keys present on the desired series. |
| Applying byte units to counts or already-converted KiB. | Check source and result units first. |
| Running `--dry-run` and expecting datapoints. | Dry-run only prints generated SignalFlow. |
| Expecting local webhook `send-test` to validate Splunk delivery. | Test local, public tunnel, and Splunk integration separately. |

For module ownership and implementation flows, see [Architecture](architecture.md).
For environment variables, deployment/security considerations, and cURL examples,
see the [User Reference](reference.md). Return to the [README](../README.md) for the quick start.
