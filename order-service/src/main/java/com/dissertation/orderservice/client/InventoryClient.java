package com.dissertation.orderservice.client;

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
}