package com.dissertation.inventoryservice.domain;

import jakarta.persistence.*;
import lombok.Getter;
import lombok.NoArgsConstructor;
import java.math.BigDecimal;
import java.util.UUID;

@Entity
@Table(name = "inventory_items")
@Getter
@NoArgsConstructor
public class InventoryItem {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    private UUID id;

    @Column(unique = true, nullable = false, length = 50)
    private String sku;

    @Column(nullable = false)
    private String name;

    @Column(precision = 10, scale = 2, nullable = false)
    private BigDecimal price;

    @Column(nullable = false)
    private Integer quantity;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false)
    private ItemStatus status;

    @Version
    private Long version;

    public InventoryItem(String sku, String name, BigDecimal price, Integer quantity) {
        this.sku = sku;
        this.name = name;
        this.price = price;
        this.quantity = quantity;
        this.status = ItemStatus.IN_STOCK;
    }

    public void reserve(int qty) {
        if (this.status != ItemStatus.IN_STOCK)
            throw new IllegalStateException("Item not available: " + this.status);
        if (this.quantity < qty)
            throw new IllegalStateException("Insufficient stock for SKU: " + this.sku);
        this.quantity -= qty;
        if (this.quantity == 0) this.status = ItemStatus.OUT_OF_STOCK;
    }

    public void restock(int qty) {
        if (qty <= 0)
            throw new IllegalArgumentException("Restock quantity must be positive");
        this.quantity += qty;
        if (this.status == ItemStatus.OUT_OF_STOCK) this.status = ItemStatus.IN_STOCK;
    }
}