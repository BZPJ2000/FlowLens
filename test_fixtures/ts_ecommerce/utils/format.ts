// Formatting utilities — used by pages, stores, and services
import type { CartItem, OrderSummary, ShippingInfo } from "../types/models";

export function formatCurrency(
  amount: number,
  currency: "CNY" | "USD" | "EUR" = "CNY"
): string {
  const symbols: Record<string, string> = { CNY: "¥", USD: "$", EUR: "€" };
  const symbol = symbols[currency] || "¥";
  return `${symbol}${amount.toFixed(2)}`;
}

export function formatDate(timestamp: number, locale: string = "zh-CN"): string {
  return new Date(timestamp).toLocaleDateString(locale, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatCartItemSummary(item: CartItem): string {
  const extras = item.selectedOptions
    .filter((o) => o.priceModifier > 0)
    .map((o) => o.optionValue)
    .join(", ");
  const base = `${item.name} × ${item.quantity}`;
  return extras ? `${base} (${extras})` : base;
}

export function formatShippingAddress(shipping: ShippingInfo): string {
  return `${shipping.province}${shipping.city}${shipping.district} ${shipping.address}\n收件人: ${shipping.receiverName} ${shipping.phone}`;
}

export function formatOrderNumber(orderId: string): string {
  return `#ORD-${orderId.slice(0, 8).toUpperCase()}`;
}

export function formatDiscountLabel(
  couponCode: string | null,
  discountAmount: number
): string {
  if (!couponCode || discountAmount <= 0) return "无优惠";
  return `优惠券 ${couponCode} (-${formatCurrency(discountAmount)})`;
}

export function truncateText(text: string, maxLength: number = 50): string {
  if (text.length <= maxLength) return text;
  return text.slice(0, maxLength - 3) + "...";
}
