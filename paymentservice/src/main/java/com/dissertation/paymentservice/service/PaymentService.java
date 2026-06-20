package com.dissertation.paymentservice.service;

import com.dissertation.paymentservice.domain.Payment;
import com.dissertation.paymentservice.repository.PaymentRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.util.List;
import java.util.UUID;

@Service
public class PaymentService {

    private final PaymentRepository paymentRepository;

    public PaymentService(PaymentRepository paymentRepository) {
        this.paymentRepository = paymentRepository;
    }

    @Transactional
    public Payment processPayment(UUID orderId, BigDecimal amount, String currency) {
        Payment payment = new Payment(orderId, amount, currency);

        // Simulate processing: amounts over 10,000 fail (useful for chaos testing later)
        if (amount.compareTo(new BigDecimal("10000")) > 0) {
            payment.fail();
        } else {
            payment.complete();
        }

        return paymentRepository.save(payment);
    }

    @Transactional(readOnly = true)
    public Payment getById(UUID id) {
        return paymentRepository.findById(id)
                .orElseThrow(() -> new IllegalArgumentException("Payment not found: " + id));
    }

    @Transactional(readOnly = true)
    public List<Payment> getByOrderId(UUID orderId) {
        return paymentRepository.findByOrderId(orderId);
    }
}