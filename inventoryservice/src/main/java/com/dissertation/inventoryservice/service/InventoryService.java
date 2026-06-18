package com.dissertation.inventoryservice.service;

import com.dissertation.inventoryservice.domain.InventoryItem;
import com.dissertation.inventoryservice.domain.ItemStatus;
import com.dissertation.inventoryservice.exception.InsufficientStockException;
import com.dissertation.inventoryservice.repository.InventoryRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.util.List;

@Service
@RequiredArgsConstructor
public class InventoryService {

    private final InventoryRepository inventoryRepository;

    public List<InventoryItem> getAllItems() {
        return inventoryRepository.findAll();
    }

    public InventoryItem getItemBySku(String sku) {
        return inventoryRepository.findBySku(sku)
                .orElseThrow(() -> new IllegalArgumentException("Item not found: " + sku));
    }

    @Transactional
    public InventoryItem createItem(String sku, String name, BigDecimal price, Integer quantity) {
        InventoryItem item = new InventoryItem(sku, name, price, quantity);
        return inventoryRepository.save(item);
    }

    @Transactional
    public InventoryItem reserveStock(String sku, int quantity) {
        InventoryItem item = inventoryRepository.findBySku(sku)
                .orElseThrow(() -> new IllegalArgumentException("Item not found: " + sku));
        item.reserve(quantity);
        return inventoryRepository.save(item);
    }

    @Transactional
    public InventoryItem restockItem(String sku, int quantity) {
        InventoryItem item = inventoryRepository.findBySku(sku)
                .orElseThrow(() -> new IllegalArgumentException("Item not found: " + sku));
        item.restock(quantity);
        return inventoryRepository.save(item);
    }
}