// Order Service
import { getUserProfile } from './user-service';
import { getProducts, updateStock } from './product-service';
import { processPayment } from './payment-service';
import { sendNotification } from './notification-service';
import { publishEvent } from './event-bus';
import { createOrderRecord, getOrderById, updateOrderStatus } from './database';

export interface Order {
  id: string;
  userId: string;
  items: OrderItem[];
  totalAmount: number;
  status: OrderStatus;
  createdAt: Date;
  updatedAt: Date;
}

export interface OrderItem {
  productId: string;
  quantity: number;
  price: number;
  name: string;
}

export type OrderStatus = 'pending' | 'confirmed' | 'processing' | 'shipped' | 'delivered' | 'cancelled';

export async function createOrder(userId: string, items: OrderItem[]): Promise<Order> {
  const user = await getUserProfile(userId);
  if (!user) throw new Error('User not found');

  // Validate stock
  for (const item of items) {
    const available = await checkStock(item.productId, item.quantity);
    if (!available) {
      throw new Error(`Insufficient stock for product ${item.productId}`);
    }
  }

  const totalAmount = items.reduce((sum, item) => sum + item.price * item.quantity, 0);

  const order: Order = {
    id: generateOrderId(),
    userId,
    items,
    totalAmount,
    status: 'pending',
    createdAt: new Date(),
    updatedAt: new Date(),
  };

  await createOrderRecord(order);

  // Reserve stock
  for (const item of items) {
    await updateStock(item.productId, -item.quantity);
  }

  await publishEvent('order.created', { orderId: order.id, userId });
  await sendNotification(userId, `Order ${order.id} created successfully`);

  return order;
}

export async function confirmOrder(orderId: string): Promise<Order> {
  const order = await getOrderById(orderId);
  if (!order) throw new Error('Order not found');

  order.status = 'confirmed';
  order.updatedAt = new Date();

  await updateOrderStatus(orderId, 'confirmed');
  await publishEvent('order.confirmed', { orderId });
  await sendNotification(order.userId, `Order ${orderId} confirmed`);

  return order;
}

export async function shipOrder(orderId: string, trackingNumber: string): Promise<Order> {
  const order = await getOrderById(orderId);
  if (!order) throw new Error('Order not found');

  order.status = 'shipped';
  order.updatedAt = new Date();

  await updateOrderStatus(orderId, 'shipped');
  await publishEvent('order.shipped', { orderId, trackingNumber });
  await sendNotification(order.userId, `Order ${orderId} shipped. Tracking: ${trackingNumber}`);

  return order;
}

export async function cancelOrder(orderId: string): Promise<Order> {
  const order = await getOrderById(orderId);
  if (!order) throw new Error('Order not found');

  if (order.status !== 'pending') {
    throw new Error('Cannot cancel order in current status');
  }

  // Restore stock
  for (const item of order.items) {
    await updateStock(item.productId, item.quantity);
  }

  order.status = 'cancelled';
  order.updatedAt = new Date();

  await updateOrderStatus(orderId, 'cancelled');
  await publishEvent('order.cancelled', { orderId });
  await sendNotification(order.userId, `Order ${orderId} cancelled`);

  return order;
}

async function checkStock(productId: string, quantity: number): Promise<boolean> {
  const products = await getProducts();
  const product = products.find(p => p.id === productId);
  return product ? product.stock >= quantity : false;
}

function generateOrderId(): string {
  return `ORD-${Date.now()}-${Math.random().toString(36).substr(2, 6).toUpperCase()}`;
}

export async function getOrdersByUser(userId: string): Promise<Order[]> {
  return [];
}
