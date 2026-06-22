package com.dissertation.orderservice.client;

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
}