// 核心类型定义
export interface User {
  id: string;
  email: string;
  name: string;
  role: UserRole;
  createdAt: Date;
}

export type UserRole = 'admin' | 'customer' | 'vendor';

export interface Product {
  id: string;
  name: string;
  price: number;
  stock: number;
  category: string;
  vendorId: string;
  tags: string[];
}

export interface CartItem {
  productId: string;
  quantity: number;
  price: number;
  product?: Product;
}

export interface Cart {
  userId: string;
  items: CartItem[];
  totalAmount: number;
  discount?: Discount;
}

export interface Order {
  id: string;
  userId: string;
  items: CartItem[];
  totalAmount: number;
  status: OrderStatus;
  paymentId?: string;
  shippingAddress: Address;
  createdAt: Date;
}

export type OrderStatus = 'pending' | 'paid' | 'shipped' | 'delivered' | 'cancelled';

export interface Address {
  street: string;
  city: string;
  state: string;
  zipCode: string;
  country: string;
}

export interface Payment {
  id: string;
  orderId: string;
  amount: number;
  method: PaymentMethod;
  status: PaymentStatus;
  transactionId?: string;
}

export type PaymentMethod = 'credit_card' | 'paypal' | 'bank_transfer';
export type PaymentStatus = 'pending' | 'completed' | 'failed' | 'refunded';

export interface Discount {
  code: string;
  percentage: number;
  maxAmount?: number;
}

export interface Notification {
  id: string;
  userId: string;
  type: NotificationType;
  message: string;
  read: boolean;
  createdAt: Date;
}

export type NotificationType = 'order' | 'payment' | 'shipping' | 'promotion';

export interface ApiResponse<T> {
  success: boolean;
  data?: T;
  error?: string;
  timestamp: Date;
}
