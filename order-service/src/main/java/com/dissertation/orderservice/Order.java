package com.dissertation.orderservice;

import jakarta.persistence.*;
import lombok.Getter;
import lombok.NoArgsConstructor;

import java.util.UUID;

@Entity
@Table(name = "orders")
@Getter
@NoArgsConstructor
public class Order {
    @Id
    private String orderId;

    @Enumerated(EnumType.STRING)
    private OrderStatus orderStatus;

    private double totalAmount;

    public Order(double totalAmount){
        this.orderId = UUID.randomUUID().toString();
        this.totalAmount = totalAmount;
        this.orderStatus = OrderStatus.PENDING;
    }

    public void confirm(){
        if(orderStatus != OrderStatus.PENDING){
            throw new IllegalStateException("Only Pending Orders can be confirmed.");
        }
        this.orderStatus = OrderStatus.CONFIRMED;
    }

    public void cancel(){
        if(orderStatus != OrderStatus.CONFIRMED){
            throw new IllegalStateException("Only Confirmed Orders can be cancelled.");
        }
        this.orderStatus = OrderStatus.CANCELLED;
    }

    public void complete(){
        if(orderStatus != OrderStatus.CONFIRMED){
            throw new IllegalStateException("Only Confirmed Orders can be completed.");
        }
        this.orderStatus = OrderStatus.COMPLETED;
    }

}
