package com.dissertation.orderservice;

import com.dissertation.orderservice.client.InventoryClient;
import com.dissertation.orderservice.client.PaymentClient;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.util.List;
import java.util.UUID;

@Service
@RequiredArgsConstructor
public class OrderService {

    private final OrderRepository orderRepository;
    private final InventoryClient inventoryClient;
    private final PaymentClient paymentClient;

    @Transactional
    public Order placeOrder(String sku, int quantity, BigDecimal totalAmount) {
        Order order = new Order(sku, quantity, totalAmount);
        order = orderRepository.save(order);

        boolean stockReserved = inventoryClient.reserveStock(sku, quantity);
        if (!stockReserved) {
            order.fail();
            orderRepository.save(order);
            throw new IllegalStateException("Insufficient stock for SKU: " + sku);
        }

        PaymentClient.PaymentResult result =
                paymentClient.processPayment(order.getId(), totalAmount);

        if (!result.isCompleted()) {
            order.fail();
            orderRepository.save(order);
            throw new IllegalStateException("Payment declined for order: " + order.getId());
        }

        order.confirm();
        return orderRepository.save(order);
    }

    @Transactional(readOnly = true)
    public Order getOrder(UUID id) {
        return orderRepository.findById(id)
                .orElseThrow(() -> new IllegalArgumentException("Order not found: " + id));
    }

    @Transactional(readOnly = true)
    public List<Order> getAllOrders() {
        return orderRepository.findAll();
    }

    @Transactional
    public Order cancelOrder(UUID id) {
        Order order = getOrder(id);
        order.cancel();
        return orderRepository.save(order);
    }
}