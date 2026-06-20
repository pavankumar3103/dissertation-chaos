package com.dissertation.paymentservice.controller;

import com.dissertation.paymentservice.domain.Payment;
import com.dissertation.paymentservice.service.PaymentService;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Positive;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.*;

import java.math.BigDecimal;
import java.util.List;
import java.util.UUID;

@RestController
@RequestMapping("/payments")
public class PaymentController {

    private final PaymentService paymentService;

    public PaymentController(PaymentService paymentService) {
        this.paymentService = paymentService;
    }

    public record ProcessPaymentRequest(
            @NotNull UUID orderId,
            @NotNull @Positive BigDecimal amount,
            @NotNull String currency
    ) {}

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    public Payment processPayment(@Valid @RequestBody ProcessPaymentRequest request) {
        return paymentService.processPayment(
                request.orderId(),
                request.amount(),
                request.currency()
        );
    }

    @GetMapping("/{id}")
    public Payment getById(@PathVariable UUID id) {
        return paymentService.getById(id);
    }

    @GetMapping("/order/{orderId}")
    public List<Payment> getByOrderId(@PathVariable UUID orderId) {
        return paymentService.getByOrderId(orderId);
    }
}