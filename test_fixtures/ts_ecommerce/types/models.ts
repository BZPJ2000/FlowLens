// Core data types used across the entire application
// This file is the central type hub - nearly every file imports from here

export interface UserProfile {
  id: string;
  email: string;
  displayName: string;
  avatarUrl: string;
  preferences: UserPreferences;
  createdAt: number;
}

export interface UserPreferences {
  theme: "light" | "dark";
  currency: "CNY" | "USD" | "EUR";
  language: "zh" | "en";
  notificationsEnabled: boolean;
}

export interface CartItem {
  productId: string;
  sku: string;
  name: string;
  price: number;
  quantity: number;
  selectedOptions: ProductOption[];
  thumbnailUrl: string;
  addedAt: number;
}

export interface ProductOption {
  optionName: string;
  optionValue: string;
  priceModifier: number;
}

export interface OrderSummary {
  orderId: string;
  userId: string;
  items: CartItem[];
  subtotal: number;
  shipping: ShippingInfo;
  taxRate: number;
  taxAmount: number;
  couponCode: string | null;
  discountAmount: number;
  totalAmount: number;
  paymentMethod: PaymentMethod;
  status: OrderStatus;
  placedAt: number;
}

export type OrderStatus = "pending" | "paid" | "shipped" | "delivered" | "cancelled" | "refunded";

export type PaymentMethod = "wechat" | "alipay" | "credit_card" | "debit_card" | "paypal";

export interface ShippingInfo {
  receiverName: string;
  phone: string;
  province: string;
  city: string;
  district: string;
  address: string;
  zipCode: string;
  shippingMethod: "standard" | "express" | "same_day";
  shippingFee: number;
  estimatedDays: number;
  trackingNumber: string | null;
}

export interface ApiResponse<T> {
  code: number;
  message: string;
  data: T | null;
  timestamp: number;
  requestId: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  pageSize: number;
  hasMore: boolean;
}

export interface AuthToken {
  accessToken: string;
  refreshToken: string;
  expiresIn: number;
  tokenType: "Bearer";
}

export interface ApiError {
  code: number;
  message: string;
  details: Record<string, string>;
  stackTrace?: string;
}
