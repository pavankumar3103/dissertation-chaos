# Concepts Primer — Read This First

## 1. Why microservices fail differently than a single app

In a single app (a monolith), when one part of your code calls another part, it's just a function call — it either runs or it crashes, instantly, on the same machine. There's no "the function was a bit slow today" or "the function didn't answer."

This dissertation's system is three separate programs — order-service, inventory-service, payment-service — running as separate processes, talking to each other over the network (HTTP), usually in separate Docker containers. The moment you put a network between two pieces of code, a whole new category of failure becomes possible that simply cannot happen inside a single app: a request can time out without ever being answered, a connection can get dropped halfway through, a service can be running but responding very slowly, or a service can be completely down while its neighbours are perfectly healthy.

Concretely: when order-service calls payment-service to charge a customer, in a monolith that's one function call that either returns a result or throws an exception you catch immediately. Here, it's a network request that might take 50ms, or 5 seconds, or might never come back at all — and order-service has to decide what to do in each of those cases. That decision-making is exactly what Circuit Breaker, Bulkhead, and Retry are for (see Section 3).

## 2. What is chaos engineering and why deliberately break things

The core idea of chaos engineering: you don't actually know whether your system is resilient until you've tested it against real failure conditions — not just the "happy path" tests most teams write (where every service responds correctly and on time).

Most testing proves a system works when everything is fine. Chaos engineering instead asks: what happens when something *isn't* fine — a service goes down, a network connection turns sluggish, a downstream dependency starts erroring? Rather than waiting for that to happen for real in production (at 3am, with customers watching), you deliberately and safely trigger it yourself, in a controlled environment, and watch what happens. If the system handles it gracefully, you've proven something real. If it falls over, you've found a problem before a customer did.

This dissertation's whole experimental design is built on that idea: trigger four specific kinds of failure (Section 6), on purpose, repeatedly, and measure whether adding Circuit Breaker / Bulkhead / Retry actually changes the outcome compared to having no protection at all.

## 3. The three resilience patterns, in plain terms (no code)

**Circuit Breaker** — like an electrical fuse. If a downstream service keeps failing, the circuit breaker "trips" (opens) and stops sending it any more requests for a while, instead failing fast and giving an immediate error. This protects two things at once: it stops hammering a service that's already struggling (giving it room to recover), and it stops the calling service from wasting time and resources waiting on calls that were going to fail anyway. After a cooldown period, it lets a few test requests through to see if the downstream service has recovered before fully reopening.

**Bulkhead** — named after the watertight compartments in a ship's hull. If one compartment floods, the doors between compartments keep the water from spreading and sinking the whole ship. Applied to software: you give each downstream dependency (e.g. inventory calls, payment calls) its own limited pool of resources (threads/concurrent calls). If inventory-service is having problems and its calls pile up, they can only consume *their own* allocated pool — they can't eat up so many resources that payment-service calls (which are working fine) get starved too.

**Retry** — simply trying the request again if it fails, on the theory that many failures are transient (a brief network blip, a momentary spike in load) and will succeed on a second attempt. The catch: naive retry can actively make things worse. If a service is already overwhelmed and failing because it's overloaded, every client automatically retrying just adds more load on top of an already-struggling service — a "retry storm" that can turn a minor slowdown into a full outage. This is exactly why Retry is usually combined with Circuit Breaker (so retries stop once the breaker trips) rather than used alone.

## 4. What Toxiproxy actually is

Toxiproxy is a proxy — a piece of software that deliberately sits in the middle of a network connection between two services, on purpose, so that a script (or a person) can tell it things like "add 2 seconds of delay to every request" or "drop every connection instantly" on command, and then turn that behaviour off again just as easily.

In this project, normally order-service would talk directly to inventory-service and payment-service. Instead, those calls are routed through Toxiproxy first. Toxiproxy mostly just passes traffic through unchanged — until one of the chaos scripts tells it to misbehave, at which point it starts injecting the requested fault. This means real, observable network failure can be triggered and removed on demand, without touching a single line of code in the actual services.

## 5. What Gatling actually is

Gatling is a load-testing tool — software that simulates a large number of users hitting a system at the same time, so you can observe how the system behaves under realistic concurrent traffic rather than just one request at a time.

In this project, Gatling simulates up to 50 "customers" placing orders simultaneously, ramping up gradually and then holding steady for several minutes, recording how long every single request took and whether it succeeded or failed. This matters because some of the resilience patterns — Bulkhead in particular — only do anything meaningful under concurrent load; testing them with one request at a time would never reveal whether they actually work.

## 6. How the four chaos scenarios map to real production incidents

- **Service Termination** — the downstream service is completely unreachable. Real-world equivalent: a service crashes, a container gets killed, or a deploy goes wrong and the new version never comes up.
- **Latency Injection** — both downstream services become uniformly slow but not dead. Real-world equivalent: a database under heavy load, or a service running on starved/throttled infrastructure, that's technically "up" but answers everything sluggishly.
- **Partial Failure** — only one downstream service degrades while the other stays healthy. Real-world equivalent: the much more common real incident — a single dependency (e.g. a third-party payment provider, or one regional database) has a bad day while everything else is fine; the question is whether the failure stays contained to that one path.
- **Cascading Failure** — one service degrades first, and shortly after, a second service degrades too. Real-world equivalent: a slow database query backs up the threads/connections of every service waiting on it, which then run out of capacity to serve their own callers, so the slowdown spreads outward from the original problem until the whole system grinds to a halt.

## 7. The big picture: what question is this dissertation answering

In one sentence: does adding a given resilience pattern — Circuit Breaker, Bulkhead, Retry, or all three combined — actually make a measurable, statistically significant difference to how well a system survives a specific kind of failure, compared to having no protection at all, and is that difference big enough and consistent enough to matter?

To answer that rigorously rather than anecdotally, the experiment runs every combination of 5 resilience configurations (none, circuit-breaker, bulkhead, retry, combined) against all 4 chaos scenarios above, 20 times each (5 × 4 × 20 = 400 trials), measuring error propagation rate, recovery time, p99 latency, throughput degradation, and resource consumption each time. Running each combination 20 times — rather than once — is what allows statistical tests (ANOVA/Kruskal-Wallis) to say with confidence whether an observed difference is a real effect of the resilience pattern, or just noise. That's the whole dissertation in one breath: not "does Circuit Breaker sound like it should help" but "here is the measured, repeated evidence for whether it actually does, and by how much."

(Design note: retry-with-backoff was originally only tested mixed into "combined" alongside circuit breaker and bulkhead — a standalone "retry" profile was added on 2026-07-01, after the other four were already verified, specifically so retry's own contribution could be isolated rather than only ever seen bundled with the other two patterns.)
