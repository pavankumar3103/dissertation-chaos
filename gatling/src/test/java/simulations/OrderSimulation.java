package simulations;

import static io.gatling.javaapi.core.CoreDsl.*;
import static io.gatling.javaapi.http.HttpDsl.*;

import io.gatling.javaapi.core.*;
import io.gatling.javaapi.http.*;

import java.time.Duration;

/**
 * Phase 8 — Gatling load testing harness.
 *
 * Drives load through the order placement flow:
 *   POST /orders  ->  Gateway (:8080)  ->  order-service  ->  inventory-service / payment-service
 *
 * order-service's PlaceOrderRequest only accepts {sku, quantity, totalAmount} — there is no
 * customerId field on the API, and Spring's default Jackson config rejects unknown JSON
 * properties with a 400, so the request body intentionally omits it.
 *
 * totalAmount is kept under 10,000 to avoid payment-service's deterministic
 * "amount > 10,000 auto-fails" rule (see Phase 3), so that under the "none" resilience
 * profile and zero chaos, requests succeed cleanly — failures observed during actual
 * trials should come from the injected chaos scenario, not from this fixed test data.
 *
 * PREREQUISITE: inventory-service must have a stock row for SKU-001 with quantityAvailable
 * high enough to cover a full trial (worst case ~50 users x ~1 req/s x 5.5 min = thousands
 * of units) before running this simulation, or every request will fail at the reserve-stock
 * step with 409 regardless of chaos/resilience configuration. There is currently no seed
 * data for SKU-001 in init-db.sql — seed inventory_db manually or via the Phase 10 experiment
 * runner's database reset step before running this.
 *
 * Run:
 *   mvn gatling:test
 *   mvn gatling:test -DbaseUrl=http://localhost:8080
 *   mvn gatling:test -DtargetUsers=50 -DrampSeconds=30 -DsustainMinutes=5
 *
 * Results: gatling/target/gatling/<run-id>/ (HTML report + simulation.log).
 * simulation.log is tab-separated and is what Phase 10/11 should parse for
 * response time p50/p95/p99, error rate, and throughput rather than re-deriving
 * them from the HTML report.
 */
public class OrderSimulation extends Simulation {

  // ── parameters (overridable via -Dname=value, matches Phase 10's automated runner) ──

  private static final String BASE_URL = System.getProperty("baseUrl", "http://localhost:8080");
  private static final int TARGET_USERS = Integer.getInteger("targetUsers", 50);
  private static final int RAMP_SECONDS = Integer.getInteger("rampSeconds", 30);
  private static final int SUSTAIN_MINUTES = Integer.getInteger("sustainMinutes", 5);

  // ── HTTP protocol ──

  private static final HttpProtocolBuilder httpProtocol =
      http.baseUrl(BASE_URL)
          .acceptHeader("application/json")
          .contentTypeHeader("application/json")
          .userAgentHeader("gatling-dissertation-chaos/1.0");

  // ── request body ──
  // sku/quantity/totalAmount are fixed and well under the payment auto-fail threshold,
  // so the experimental variable is the chaos scenario + resilience pattern, not the payload.

  private static final String ORDER_BODY =
      "{ \"sku\": \"SKU-001\", \"quantity\": 1, \"totalAmount\": 99.99 }";

  // ── scenario ──

  private static final ScenarioBuilder placeOrder =
      scenario("Place Order")
          .exec(
              http("POST /orders")
                  .post("/orders")
                  .body(StringBody(ORDER_BODY))
                  .check(status().is(201)));

  // ── injection profile (closed workload model: ramp to N concurrent users, then hold) ──
  //
  //   Ramp:      0  -> TARGET_USERS concurrent users over RAMP_SECONDS
  //   Sustained: TARGET_USERS concurrent users for SUSTAIN_MINUTES
  //
  // Defaults (50 users / 30s ramp / 5min sustain) match the dissertation's load profile.
  // In-flight requests are allowed to drain naturally after injection ends, which accounts
  // for the ~7.5 minute total wall-clock time per trial referenced in the experimental design.

  {
    setUp(
            placeOrder.injectClosed(
                rampConcurrentUsers(0).to(TARGET_USERS).during(Duration.ofSeconds(RAMP_SECONDS)),
                constantConcurrentUsers(TARGET_USERS).during(Duration.ofMinutes(SUSTAIN_MINUTES))))
        .protocols(httpProtocol);
  }
}
