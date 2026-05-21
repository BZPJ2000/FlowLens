// 订单处理服务
import { Order, OrderStatus, Address, CartItem, ApiResponse } from './types';
import { generateId, createApiResponse, createErrorResponse, formatCurrency } from './utils';
import { getCart, clearCart, validateCartStock } from './cart';
import { updateStock } from './product';
import { getUserById } from './auth';
import { processPayment } from './payment';
import { sendOrderConfirmation, sendOrderStatusUpdate } from './notification';

// 模拟订单数据库
const orders: Map<string, Order> = new Map();

export function createOrder(userId: string, shippingAddress: Address): ApiResponse<Order> {
  const user = getUserById(userId);
  if (!user) {
    return createErrorResponse('User not found');
  }

  const cartResponse = getCart(userId);
  if (!cartResponse.success || !cartResponse.data) {
    return createErrorResponse('Cart not found');
  }

  const cart = cartResponse.data;

  if (cart.items.length === 0) {
    return createErrorResponse('Cart is empty');
  }

  // 验证库存
  const stockValidation = validateCartStock(userId);
  if (!stockValidation.success) {
    return stockValidation as ApiResponse<Order>;
  }

  const order: Order = {
    id: generateId(),
    userId,
    items: cart.items.map(item => ({ ...item })),
    totalAmount: cart.totalAmount,
    status: 'pending',
    shippingAddress,
    createdAt: new Date(),
  };

  orders.set(order.id, order);

  // 减少库存
  for (const item of order.items) {
    updateStock(item.productId, -item.quantity);
  }

  // 清空购物车
  clearCart(userId);

  // 发送订单确认通知
  sendOrderConfirmation(userId, order.id, order.totalAmount);

  return createApiResponse(order);
}

export function getOrderById(orderId: string): ApiResponse<Order> {
  const order = orders.get(orderId);

  if (!order) {
    return createErrorResponse('Order not found');
  }

  return createApiResponse(order);
}

export function getUserOrders(userId: string): ApiResponse<Order[]> {
  const userOrders = Array.from(orders.values()).filter(o => o.userId === userId);
  return createApiResponse(userOrders);
}

export function updateOrderStatus(orderId: string, status: OrderStatus): ApiResponse<Order> {
  const order = orders.get(orderId);

  if (!order) {
    return createErrorResponse('Order not found');
  }

  const oldStatus = order.status;
  order.status = status;

  // 发送状态更新通知
  sendOrderStatusUpdate(order.userId, orderId, oldStatus, status);

  return createApiResponse(order);
}

export function cancelOrder(orderId: string, userId: string): ApiResponse<Order> {
  const order = orders.get(orderId);

  if (!order) {
    return createErrorResponse('Order not found');
  }

  if (order.userId !== userId) {
    return createErrorResponse('Unauthorized');
  }

  if (order.status !== 'pending') {
    return createErrorResponse('Cannot cancel order in current status');
  }

  // 恢复库存
  for (const item of order.items) {
    updateStock(item.productId, item.quantity);
  }

  order.status = 'cancelled';

  return createApiResponse(order);
}

export function processOrderPayment(orderId: string, paymentMethod: string): ApiResponse<Order> {
  const order = orders.get(orderId);

  if (!order) {
    return createErrorResponse('Order not found');
  }

  if (order.status !== 'pending') {
    return createErrorResponse('Order already processed');
  }

  // 处理支付
  const paymentResponse = processPayment(orderId, order.totalAmount, paymentMethod as any);

  if (!paymentResponse.success || !paymentResponse.data) {
    return createErrorResponse(paymentResponse.error || 'Payment failed');
  }

  order.paymentId = paymentResponse.data.id;
  order.status = 'paid';

  return createApiResponse(order);
}

export function getOrdersByStatus(status: OrderStatus): ApiResponse<Order[]> {
  const statusOrders = Array.from(orders.values()).filter(o => o.status === status);
  return createApiResponse(statusOrders);
}

export function getOrderTotal(orderId: string): number {
  const order = orders.get(orderId);
  return order?.totalAmount || 0;
}

export function getOrderItemCount(orderId: string): number {
  const order = orders.get(orderId);
  return order ? order.items.reduce((sum, item) => sum + item.quantity, 0) : 0;
}

export function getOrderSummary(orderId: string): ApiResponse<{
  order: Order;
  itemCount: number;
  formattedTotal: string;
}> {
  const order = orders.get(orderId);

  if (!order) {
    return createErrorResponse('Order not found');
  }

  return createApiResponse({
    order,
    itemCount: getOrderItemCount(orderId),
    formattedTotal: formatCurrency(order.totalAmount),
  });
}
