package com.dissertation.orderservice.client;

import io.github.resilience4j.bulkhead.annotation.Bulkhead;
import io.github.resilience4j.circuitbreaker.annotation.CircuitBreaker;
import io.github.resilience4j.retry.annotation.Retry;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.springframework.web.client.HttpClientErrorException;
import org.springframework.web.client.RestTemplate;

import java.util.Map;

@Component
public class InventoryClient {

    private final RestTemplate restTemplate;
    private final String baseUrl;

    public InventoryClient(RestTemplate restTemplate,
                           @Value("${services.inventory.base-url}") String baseUrl) {
        this.restTemplate = restTemplate;
        this.baseUrl = baseUrl;
    }

    @CircuitBreaker(name = "inventoryService", fallbackMethod = "reserveStockFallback")
    @Bulkhead(name = "inventoryService", fallbackMethod = "reserveStockFallback")
    @Retry(name = "inventoryService", fallbackMethod = "reserveStockFallback")
    public boolean reserveStock(String sku, int quantity) {
        try {
            String url = baseUrl + "/inventory/" + sku + "/reserve?quantity=" + quantity;
            restTemplate.patchForObject(url, null, Void.class);
            return true;
        } catch (HttpClientErrorException.Conflict e) {
            return false;
        } catch (HttpClientErrorException.NotFound e) {
            return false;
        }
    }

    public boolean reserveStockFallback(String sku, int quantity, Throwable t) {
        throw new RuntimeException("Inventory service unavailable for SKU: " + sku, t);
    }
}