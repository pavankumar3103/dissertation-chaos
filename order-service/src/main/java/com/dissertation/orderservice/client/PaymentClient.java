package com.dissertation.orderservice.client;

import io.github.resilience4j.bulkhead.annotation.Bulkhead;
import io.github.resilience4j.circuitbreaker.annotation.CircuitBreaker;
import io.github.resilience4j.retry.annotation.Retry;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestTemplate;

import java.math.BigDecimal;
import java.util.Map;
import java.util.UUID;

@Component
public class PaymentClient {

    private final RestTemplate restTemplate;
    private final String baseUrl;

    public PaymentClient(RestTemplate restTemplate,
                         @Value("${services.payment.base-url}") String baseUrl) {
        this.restTemplate = restTemplate;
        this.baseUrl = baseUrl;
    }

    public record PaymentResult(String status) {
        public boolean isCompleted() {
            return "COMPLETED".equals(status);
        }
    }

    @CircuitBreaker(name = "paymentService", fallbackMethod = "processPaymentFallback")
    @Bulkhead(name = "paymentService", fallbackMethod = "processPaymentFallback")
    @Retry(name = "paymentService", fallbackMethod = "processPaymentFallback")
    public PaymentResult processPayment(UUID orderId, BigDecimal amount) {
        String url = baseUrl + "/payments";
        var body = Map.of(
                "orderId", orderId.toString(),
                "amount", amount,
                "currency", "EUR"
        );

        @SuppressWarnings("unchecked")
        Map<String, Object> response =
                restTemplate.postForObject(url, body, Map.class);

        String status = (String) response.get("status");
        return new PaymentResult(status);
    }

    public PaymentResult processPaymentFallback(UUID orderId, BigDecimal amount, Throwable t) {
        throw new RuntimeException("Payment service unavailable for order: " + orderId, t);
    }
}