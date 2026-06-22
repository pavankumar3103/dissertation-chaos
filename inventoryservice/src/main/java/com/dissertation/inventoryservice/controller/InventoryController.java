package com.dissertation.inventoryservice.controller;

import com.dissertation.inventoryservice.domain.InventoryItem;
import com.dissertation.inventoryservice.service.InventoryService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.math.BigDecimal;
import java.util.List;

@RestController
@RequestMapping("/inventory")
@RequiredArgsConstructor
public class InventoryController {

    private final InventoryService inventoryService;

    @GetMapping
    public ResponseEntity<List<InventoryItem>> getAllItems() {
        return ResponseEntity.ok(inventoryService.getAllItems());
    }

    @GetMapping("/{sku}")
    public ResponseEntity<InventoryItem> getItemBySku(@PathVariable String sku) {
        return ResponseEntity.ok(inventoryService.getItemBySku(sku));
    }

    @PostMapping
    public ResponseEntity<InventoryItem> createItem(@RequestBody CreateItemRequest request) {
        InventoryItem item = inventoryService.createItem(
                request.sku(),
                request.name(),
                request.price(),
                request.quantityAvailable()
        );
        return ResponseEntity.status(HttpStatus.CREATED).body(item);
    }

    @PatchMapping("/{sku}/reserve")
    public ResponseEntity<InventoryItem> reserveStock(
            @PathVariable String sku,
            @RequestParam int quantity) {
        return ResponseEntity.ok(inventoryService.reserveStock(sku, quantity));
    }

    @PatchMapping("/{sku}/restock")
    public ResponseEntity<InventoryItem> restockItem(
            @PathVariable String sku,
            @RequestParam int quantity) {
        return ResponseEntity.ok(inventoryService.restockItem(sku, quantity));
    }

    public record CreateItemRequest(
            String sku,
            String name,
            BigDecimal price,
            int quantityAvailable
    ) {}
}