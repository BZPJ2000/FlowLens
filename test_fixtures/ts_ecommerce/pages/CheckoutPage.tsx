// Checkout page — the "leaf" component that consumes all upstream services
import React, { useEffect, useState } from "react";
import type { CartItem, ShippingInfo, PaymentMethod, OrderSummary } from "../types/models";
import { useCartStore } from "../stores/useCartStore";
import { formatCurrency, formatCartItemSummary, formatShippingAddress, formatDiscountLabel } from "../utils/format";
import { isAuthenticated } from "../services/auth";
import { apiClient } from "../api/client";

interface CheckoutPageProps {
  onOrderPlaced?: (orderId: string) => void;
}

const CheckoutPage: React.FC<CheckoutPageProps> = ({ onOrderPlaced }) => {
  const [selectedPayment, setSelectedPayment] = useState<PaymentMethod>("wechat");
  const [couponInput, setCouponInput] = useState("");
  const [appliedCoupon, setAppliedCoupon] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [orderPlaced, setOrderPlaced] = useState<string | null>(null);

  const cart = useCartStore;
  const { items, itemCount, subtotal, checkoutStep, shippingAddress } = cart;

  useEffect(() => {
    if (!isAuthenticated()) {
      window.location.href = "/login";
      return;
    }
    cart.initialize();
  }, []);

  const shippingFee: number =
    checkoutStep.shippingAddress?.shippingMethod === "express" ? 15.0
    : checkoutStep.shippingAddress?.shippingMethod === "same_day" ? 25.0
    : 5.0;

  const discountAmount = appliedCoupon ? subtotal * 0.1 : 0;
  const taxRate = 0.13;
  const taxAmount = Math.round((subtotal - discountAmount + shippingFee) * taxRate * 100) / 100;
  const totalAmount = subtotal - discountAmount + shippingFee + taxAmount;

  const handlePlaceOrder = async () => {
    setIsSubmitting(true);
    try {
      const orderSummary: OrderSummary = {
        orderId: "",
        userId: "",
        items: items,
        subtotal,
        shipping: shippingAddress as ShippingInfo,
        taxRate,
        taxAmount,
        couponCode: appliedCoupon,
        discountAmount,
        totalAmount,
        paymentMethod: selectedPayment,
        status: "pending",
        placedAt: Date.now(),
      };

      const response = await apiClient.submitOrder(orderSummary);
      if (response.data) {
        const orderNumber = await cart.confirmOrder();
        setOrderPlaced(orderNumber);
        onOrderPlaced?.(orderNumber);
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const applyCoupon = () => {
    if (couponInput.trim() && !appliedCoupon) {
      setAppliedCoupon(couponInput.trim().toUpperCase());
      setCouponInput("");
    }
  };

  if (orderPlaced) {
    return (
      <div className="order-success">
        <h2>订单已提交!</h2>
        <p>{orderPlaced}</p>
        <p>总金额: {formatCurrency(totalAmount)}</p>
      </div>
    );
  }

  return (
    <div className="checkout-page">
      <h1>结算 — {itemCount} 件商品</h1>

      {/* Cart items */}
      <section className="cart-items">
        {items.map((item: CartItem) => (
          <div key={item.productId} className="cart-line">
            <span>{formatCartItemSummary(item)}</span>
            <span>{formatCurrency(item.price * item.quantity)}</span>
          </div>
        ))}
      </section>

      {/* Shipping */}
      {shippingAddress?.receiverName && (
        <section className="shipping-section">
          <pre>{formatShippingAddress(shippingAddress as ShippingInfo)}</pre>
        </section>
      )}

      {/* Coupon */}
      <section className="coupon-section">
        <input value={couponInput} onChange={(e) => setCouponInput(e.target.value)} />
        <button onClick={applyCoupon}>使用优惠券</button>
        {appliedCoupon && (
          <span>{formatDiscountLabel(appliedCoupon, discountAmount)}</span>
        )}
      </section>

      {/* Payment */}
      <section>
        {(["wechat", "alipay", "credit_card"] as PaymentMethod[]).map((method) => (
          <label key={method}>
            <input
              type="radio"
              checked={selectedPayment === method}
              onChange={() => setSelectedPayment(method)}
            />
            {method}
          </label>
        ))}
      </section>

      {/* Summary */}
      <div className="order-total">
        <div>小计: {formatCurrency(subtotal)}</div>
        {discountAmount > 0 && <div>优惠: -{formatCurrency(discountAmount)}</div>}
        <div>运费: {formatCurrency(shippingFee)}</div>
        <div>税费: {formatCurrency(taxAmount)}</div>
        <div>总计: {formatCurrency(totalAmount)}</div>
      </div>

      <button onClick={handlePlaceOrder} disabled={isSubmitting}>
        {isSubmitting ? "提交中..." : "提交订单"}
      </button>
    </div>
  );
};

export default CheckoutPage;
