# MCP timeout investigation

Date: 2026-11-06. Measurements recorded in UTC.

## Conclusion

The reproduced 30-second failures are caused by slow Wikipedia retrieval behind
Otari, with Wikipedia returning HTTP 429 and the Wikipedia client waiting and
retrying. Both the notebook function and curl through Otari return HTTP 504 at
approximately 30 seconds. This is not a Python-only timeout or a missing TCP
keep-alive setting.

Direct MCP can remain open much longer: a valid Venus summary took 76.22 seconds.
A Mercury request was still incomplete at curl's 90-second limit. Reusing an
already-open connection saved approximately 0.09 seconds on cached requests, not
the tens of seconds spent waiting for upstream retries.

The exact Otari component/configuration enforcing its deadline was not inspected.
The historical November 5 failure cannot be conclusively attributed to the same
upstream response, but the same error was reproduced with contemporaneous
Wikipedia rate-limit evidence.

## Infrastructure prerequisite

Initially the existing AKS cluster was **Stopped**, not absent. The full notebook
function failed during discovery after 5.219 seconds with HTTP 502,
`mcp_connection_failed`, and execution state `not_started`. The direct public MCP
connection timed out, and the stopped AKS API hostname did not resolve.

With explicit approval, the existing cluster was started:

```bash
az aks start -g rg-italy -n otari-hack-aks
```

No Bicep deployment was necessary. The existing MCP pod returned to 2/2 Running,
and unauthenticated HTTPS returned the expected 401. Final checks confirmed the
cluster remained Running and the pod healthy. **AKS was left running and incurs
normal compute charges.**

[main.bicep](./main.bicep) compiled, with warnings about unavailable preview API
schemas and other lint issues. Compilation was not proof of deployment validity;
no ARM deployment was attempted.

## Method

The actual definitions of `get_mcp_tools`, `execute_mcp_tool`, and `assert_fact_v2`
were loaded from [the notebook](../Prototype/api.ipynb) and executed in the project
virtual environment. Notebook source and stored outputs were not edited. This
was execution of notebook code in a terminal harness, not a VS Code kernel run.

Compared paths:

1. Notebook `execute_mcp_tool` using the installed Otari SDK and its persistent
   client.
2. curl POST to Otari `/api/v1/mcp/execute`, with the same live server revision,
   tool name, and arguments.
3. Authenticated curl directly to the public Wikipedia `/mcp` endpoint, with MCP
   initialization, initialized notification, session ID, and negotiated protocol
   version before `tools/call`.

Each measured tool request was a separate execution. No curl retry option was
used. SDK/curl ordering alternated for paired trials. Initial timing trials used
separate curl processes/connections; the connection-reuse experiment explicitly
used one curl process with multiple transfers.

The full fact-check used `model="assert-claiming"`, `search=False`, and the original
Italian claim about eight planets and Pluto. Stage instrumentation added a
90-second read timeout to completion requests only; MCP execution retained the
original helper's request behavior.

Direct authentication was retrieved from the existing Kubernetes secret in
memory and supplied through curl stdin configuration. Credentials were not
printed or persisted in measurements.

## Results

### Full notebook workflow after recovery

| Stage | Seconds |
|---|---:|
| Live discovery, 22 tools | 1.271 |
| Model completion 1 | 1.188 |
| Solar System summary | 1.513 |
| Model completion 2 | 3.116 |
| Pluto summary | 1.383 |
| Model completion 3 | 2.488 |
| **Entire `assert_fact_v2` call** | **10.965** |

The final verdict was `supported`. About 6.79 seconds were model completions and
2.90 seconds were tool executions. This successful run alone would have hidden
the cold-retrieval problem.

### Warm summaries: matched inputs

Three trials per cell, before the later semantic verification pass. Values are
median wall seconds, including process startup for curl. Parentheses show range.
Setup/discovery is excluded from tool-execution timings.

| Title | Notebook SDK via Otari | curl via Otari | curl direct MCP |
|---|---:|---:|---:|
| Solar System | 0.679 (0.674-0.693) | 0.918 (0.874-0.934) | 0.134 (0.134-0.138) |
| Pluto | 0.683 (0.679-0.693) | 0.860 (0.846-0.892) | 0.111 (0.110-0.112) |

Paired catalog discovery also succeeded: SDK median 0.571 seconds versus curl
median 0.743 seconds, three trials each.

The curl-to-Otari warm summary requests reported approximately 610-667 ms in
`x-envoy-upstream-service-time`. curl TCP/TLS completion was approximately
153-170 ms for those gateway calls. Direct MCP uses a different network path,
so the difference cannot all be assigned to gateway application processing.
The SDK-versus-fresh-curl difference is consistent with connection reuse, but
these measurements do not isolate every source of overhead.

### Previously untouched title candidates: gateway failures reproduced

The first request for each title caused live Wikipedia requests in server logs.
These were not controlled cache flushes.

| Title | First SDK trial | First gateway-curl trial |
|---|---|---|
| Neptune | **504, 30.350 s** | 200, 13.630 s |
| Uranus | 200, 29.691 s | **504, 30.515 s** |
| International Astronomical Union | **504, 30.318 s** | **504, 30.552 s** |

All four 504s returned `mcp_outcome_unknown`, execution state `outcome_unknown`.
For example:

- SDK Neptune: request `req_1b584c321b5945808876d4a22f34cdae`.
- curl Uranus: request `req_55f7133d84b440f5b783653a8eff611a`;
  curl network time 30.479 s and Envoy upstream time 30,245 ms.

The first paired calls are **not independent cold samples**. A request dispatched
after a timeout may overlap the original server work, which did happen here.
They were intentional read-only benchmark executions with distinct execution
IDs, not a proposed production retry policy.

Later cached requests for these titles returned in approximately 0.68-0.71
seconds via SDK and 0.86-0.88 seconds via gateway curl.

### Direct MCP: long operations bypass the Otari deadline

| Title | First direct request | Subsequent cached requests |
|---|---|---|
| Mercury (planet) | **Incomplete at 90.023 s**, curl exit 28 | 0.141 s, 0.134 s |
| Venus | **Valid summary in 76.224 s** | 0.156 s, 0.134 s |
| Saturn | Valid summary in 0.725 s | 0.112 s, 0.111 s |

Mercury received HTTP 200 headers after about 0.092 seconds, but did not receive
a final result before curl timed out. Its 225 received bytes and HTTP status
must **not** be counted as a successful tool result. Server logs show the
Wikipedia extracts request eventually succeeded around 19:02:00 UTC, roughly
106 seconds after the tool started.

Venus also received headers quickly, after about 0.136 seconds, while the final
summary arrived much later. This distinguishes stream establishment from tool
completion and demonstrates that the direct SSE path can remain open beyond
30 seconds.

### Actual connection-reuse test

Five cached Solar System calls were sent through one curl process and MCP
session. The first transfer opened a connection; the next four reused it.

| Transfer | New connections | TCP/TLS establishment | Total network seconds |
|---|---:|---|---:|
| First | 1 | TCP 0.032 s; TLS complete 0.067 s | 0.123085 |
| Second | 0 | Both 0 | 0.031843 |
| Third | 0 | Both 0 | 0.031897 |
| Fourth | 0 | Both 0 | 0.031167 |
| Fifth | 0 | Both 0 | 0.032329 |

Reused-connection median: **0.031870 seconds**. Compared with the first transfer,
the saving was approximately **0.091 seconds**. Keep-alive is useful for
throughput and warm-request latency, but cannot solve the observed retry waits.

### Result validation

A final warm verification pass checked eight titles across SDK, gateway curl,
and direct MCP. All returned nonempty summaries, and each title's summary
SHA-256 matched across the three paths. This verifies equivalent content rather
than relying only on HTTP 200 or `isError=false`.

## Causal evidence

Targeted server logs showed this sequence:

| UTC | Event |
|---|---|
| 18:57:17.892 | Neptune tool starts; Wikipedia metadata request begins |
| 18:57:18.244 | Wikipedia returns **429 Too Many Requests** |
| 18:57:47.783 | Notebook records Otari 504 |
| 18:57:48.629 | Separate benchmark execution also receives Wikipedia 429 |
| 18:58:00.509 | Wikipedia metadata finally succeeds |
| 18:58:00.818 | Wikipedia extracts succeeds |
| 19:00:14.768 | Direct Mercury metadata receives 429 |
| 19:01:01.045 | Mercury metadata succeeds, then extracts is requested |
| 19:01:01.147 | Mercury extracts receives 429 |
| 19:02:00.489 | Mercury extracts finally succeeds |
| 19:01:44.993 | Direct Venus metadata receives 429 |
| 19:02:01.345 | Venus extracts also receives 429 |
| 19:03:00.768 | Venus extracts finally succeeds |

Inspection of the **deployed** code and runtime configuration established:

- `wikipedia-mcp` version **2.0.1**, `Wikipedia-API` version **0.16.0**.
- Summary retrieval calls `page.exists()` and then `page.summary`, generating
  separate metadata and extracts requests on the observed cold path.
- The Wikipedia HTTP client is persistent: it already uses a shared
  `httpx.Client`, not a new connection object per summary.
- Runtime HTTP timeout: **10.0 seconds**. Default `max_retries=3` permits
  **four attempts** per upstream request. Base retry wait is **1.0 second**;
  retry logic can honor `Retry-After`.
- An HTTP attempt timeout does not bound retry sleeps or the total tool
  operation. In particular, receiving a quick 429 can lead to a long wait
  without hitting a 10-second network timeout.
- Cache-enabled summary retrieval uses in-process `functools.lru_cache`,
  maximum **128 entries**. It is not a durable shared cache.
- The installed Otari SDK documents `client_execution_id` as correlation,
  **not idempotency**, and explicitly prohibits automatic execution retries.
- The high-level `OtariClient(timeout=...)` configures its streaming HTTP client.
  Notebook MCP calls use the generated API, whose separate timeout parameter is
  `_request_timeout`. Neither setting can override an upstream HTTP 504.

Actual upstream `Retry-After` header values were not captured, so the exact
source of each individual retry delay is not proven. The observed 429 responses,
long waits, eventual completion, and configured retry behavior are established.

## Recommendations, in priority order

1. **Handle upstream rate limits within the tool's execution budget.** Add a
   total deadline shorter than Otari's apparent 30-second limit, such as 20-25
   seconds including retries, waiting, metadata, extracts, and response delivery.
   If `Retry-After` cannot fit, report an explicit rate-limited/incomplete result
   instead of sleeping past the gateway deadline. Do not ignore `Retry-After` or
   increase parallelism against a rate-limited upstream.
2. **Reduce upstream work and cache stampedes.** Where compatible, fetch lead
   extracts and existence information in one MediaWiki query, requesting only
   the lead rather than retrieving the full extracts payload. Add single-flight
   coordination for identical misses. Consider a shared cache with an explicit
   freshness policy; the current cache disappears on process restart and
   evicts entries after 128 distinct keys.
3. **If long calls are intentional, change the backend contract.** Ask the Otari
   service owner which execution deadline produced `mcp_outcome_unknown`. Either
   extend that deadline and every enclosing proxy/client timeout, or use
   asynchronous submission with status/result retrieval or supported progress
   streaming. A 60-second allowance is not enough for the observed 76-106-second
   operations. Direct SSE being open does not extend the gateway execution
   budget, and no existing Otari async execution API was verified.
4. **Keep the current persistent client.** Reuse the catalog with revision-aware
   refresh, expose only necessary canonical tools rather than duplicate aliases,
   and reuse MCP sessions/connections where supported. These optimize steady
   state but do not fix Wikipedia throttling.
5. **Validate evidence failures explicitly.** The deployed summary wrapper can
   encode an error inside a successful MCP payload. Check the structured summary
   and error fields, not just HTTP status or `isError`. Ensure the final
   fact-check reports insufficient evidence when verification did not finish.
6. **Do not automatically retry outcome-unknown executions.** The experiment
   demonstrated that upstream work continues after the caller times out.
   Distinct execution IDs do not make retries idempotent.
7. **Pin the deployed package/image and instrument it.** The Dockerfile currently
   installs an unpinned package and the deployment uses `latest`. Record gateway
   request ID, execution ID, tool arguments, cache status, upstream HTTP status,
   retry count/delay, and elapsed time. Pin versions for reproducible behavior.

No production timeout, retry, caching, or notebook logic was changed during this
investigation.

## Data and limitations

[Raw measurements](./benchmark-results.json) contain 101 stage/request records,
including setup and failed pre-start discovery; they are not 101 independent
fact-checks. The recorded window is 18:31-19:35 UTC. Credential values and
Wikipedia article text are excluded.

This is a small, sequential diagnostic sample, not a load test or a population
estimate of how often calls fail. Different cold titles are not interchangeable
matched trials, caches were not flushed, and requests after unknown outcomes can
overlap original work. No cluster configuration changes, package upgrades,
cache clears, or speculative timeout changes were made. Only starting the
previously stopped cluster changed infrastructure state.
