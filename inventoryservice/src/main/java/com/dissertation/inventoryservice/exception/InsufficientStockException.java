package com.dissertation.inventoryservice.exception;

public class InsufficientStockException extends RuntimeException {
    public InsufficientStockException(String sku, int requested, int available) {
        super("Insufficient stock for SKU: " + sku +
                " — requested: " + requested +
                ", available: " + available);
    }
}
