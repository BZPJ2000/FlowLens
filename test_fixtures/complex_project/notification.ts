// 通知服务
import { Notification, NotificationType, ApiResponse } from './types';
import { generateId, createApiResponse, createErrorResponse, formatCurrency, formatDate } from './utils';
import { getUserById } from './auth';
import { OrderStatus } from './types';

// 模拟通知数据库
const notifications: Map<string, Notification> = new Map();

export function sendNotification(
  userId: string,
  message: string,
  type: NotificationType
): ApiResponse<Notification> {
  const user = getUserById(userId);

  if (!user) {
    return createErrorResponse('User not found');
  }

  const notification: Notification = {
    id: generateId(),
    userId,
    type,
    message,
    read: false,
    createdAt: new Date(),
  };

  notifications.set(notification.id, notification);

  return createApiResponse(notification);
}

export function getUserNotifications(userId: string): ApiResponse<Notification[]> {
  const userNotifications = Array.from(notifications.values())
    .filter(n => n.userId === userId)
    .sort((a, b) => b.createdAt.getTime() - a.createdAt.getTime());

  return createApiResponse(userNotifications);
}

export function getUnreadNotifications(userId: string): ApiResponse<Notification[]> {
  const unreadNotifications = Array.from(notifications.values())
    .filter(n => n.userId === userId && !n.read)
    .sort((a, b) => b.createdAt.getTime() - a.createdAt.getTime());

  return createApiResponse(unreadNotifications);
}

export function markAsRead(notificationId: string): ApiResponse<Notification> {
  const notification = notifications.get(notificationId);

  if (!notification) {
    return createErrorResponse('Notification not found');
  }

  notification.read = true;

  return createApiResponse(notification);
}

export function markAllAsRead(userId: string): ApiResponse<void> {
  Array.from(notifications.values())
    .filter(n => n.userId === userId && !n.read)
    .forEach(n => (n.read = true));

  return createApiResponse(undefined);
}

export function deleteNotification(notificationId: string): ApiResponse<void> {
  if (!notifications.has(notificationId)) {
    return createErrorResponse('Notification not found');
  }

  notifications.delete(notificationId);
  return createApiResponse(undefined);
}

// 特定业务通知函数

export function sendOrderConfirmation(userId: string, orderId: string, amount: number): void {
  const message = `Your order ${orderId} has been confirmed. Total: ${formatCurrency(amount)}`;
  sendNotification(userId, message, 'order');
}

export function sendOrderStatusUpdate(
  userId: string,
  orderId: string,
  oldStatus: OrderStatus,
  newStatus: OrderStatus
): void {
  const message = `Order ${orderId} status updated from ${oldStatus} to ${newStatus}`;
  sendNotification(userId, message, 'order');
}

export function sendPaymentConfirmation(userId: string, paymentId: string, amount: number): void {
  const message = `Payment ${paymentId} of ${formatCurrency(amount)} completed successfully`;
  sendNotification(userId, message, 'payment');
}

export function sendPaymentFailure(userId: string, paymentId: string, amount: number): void {
  const message = `Payment ${paymentId} of ${formatCurrency(amount)} failed. Please try again.`;
  sendNotification(userId, message, 'payment');
}

export function sendShippingUpdate(userId: string, orderId: string, trackingNumber: string): void {
  const message = `Your order ${orderId} has been shipped. Tracking: ${trackingNumber}`;
  sendNotification(userId, message, 'shipping');
}

export function notifyPriceChange(productId: string, oldPrice: number, newPrice: number): void {
  // 通知所有关注该产品的用户（简化实现）
  const message = `Product ${productId} price changed from ${formatCurrency(oldPrice)} to ${formatCurrency(newPrice)}`;
  // 这里应该查询关注该产品的用户列表
  console.log('Price change notification:', message);
}

export function notifyStockAlert(productId: string, stock: number): void {
  // 通知管理员库存不足
  const message = `Low stock alert: Product ${productId} has only ${stock} items left`;
  console.log('Stock alert:', message);
}

export function getNotificationCount(userId: string): number {
  return Array.from(notifications.values()).filter(n => n.userId === userId).length;
}

export function getUnreadCount(userId: string): number {
  return Array.from(notifications.values()).filter(n => n.userId === userId && !n.read).length;
}
