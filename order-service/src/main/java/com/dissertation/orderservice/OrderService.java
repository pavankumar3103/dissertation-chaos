package com.dissertation.orderservice;

import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
@RequiredArgsConstructor
public class OrderService {

    private final OrderRepository orderRepository;

    public Order placeOrder(double totalAmount) {
        Order order = new Order(totalAmount);
        return orderRepository.save(order);
    }

    public Order confirmOrder(String orderId) {
        Order order = findOrderById(orderId);
        order.confirm();
        return orderRepository.save(order);
    }

    public Order completeOrder(String orderId){
        Order order = findOrderById(orderId);
        order.complete();
        return orderRepository.save(order);
    }

    public Order cancelOrder(String orderId){
        Order order =  findOrderById(orderId);
        order.cancel();
        return orderRepository.save(order);
    }

    public List<Order> getAllOrders(){
        return orderRepository.findAll();
    }

    public Order getOrder(String orderId){
        return findOrderById(orderId);
    }
    private Order findOrderById(String orderId) {
        return orderRepository.findById(orderId)
                .orElseThrow(() -> new IllegalArgumentException("Order not found" + orderId));
    }
}
