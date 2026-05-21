// 支付处理服务
import { Payment, PaymentMethod, PaymentStatus, ApiResponse } from './types';
import { generateId, createApiResponse, createErrorResponse, delay } from './utils';
import { getOrderById, updateOrderStatus } from './order';
import { sendPaymentConfirmation, sendPaymentFailure } from './notification';

// 模拟支付数据库
const payments: Map<string, Payment> = new Map();

export async function processPayment(
  orderId: string,
  amount: number,
  method: PaymentMethod
): Promise<ApiResponse<Payment>> {
  const orderResponse = getOrderById(orderId);

  if (!orderResponse.success || !orderResponse.data) {
    return createErrorResponse('Order not found');
  }

  const order = orderResponse.data;

  if (order.totalAmount !== amount) {
    return createErrorResponse('Amount mismatch');
  }

  const payment: Payment = {
    id: generateId(),
    orderId,
    amount,
    method,
    status: 'pending',
  };

  payments.set(payment.id, payment);

  // 模拟支付处理延迟
  await delay(1000);

  // 模拟支付网关处理
  const success = await simulatePaymentGateway(method, amount);

  if (success) {
    payment.status = 'completed';
    payment.transactionId = generateId();
    updateOrderStatus(orderId, 'paid');
    sendPaymentConfirmation(order.userId, payment.id, amount);
  } else {
    payment.status = 'failed';
    sendPaymentFailure(order.userId, payment.id, amount);
  }

  return createApiResponse(payment);
}

async function simulatePaymentGateway(method: PaymentMethod, amount: number): Promise<boolean> {
  // 模拟不同支付方式的成功率
  const successRates: Record<PaymentMethod, number> = {
    credit_card: 0.95,
    paypal: 0.98,
    bank_transfer: 0.90,
  };

  await delay(500);

  return Math.random() < successRates[method];
}

export function getPaymentById(paymentId: string): ApiResponse<Payment> {
  const payment = payments.get(paymentId);

  if (!payment) {
    return createErrorResponse('Payment not found');
  }

  return createApiResponse(payment);
}

export function getPaymentsByOrder(orderId: string): ApiResponse<Payment[]> {
  const orderPayments = Array.from(payments.values()).filter(p => p.orderId === orderId);
  return createApiResponse(orderPayments);
}

export async function refundPayment(paymentId: string): Promise<ApiResponse<Payment>> {
  const payment = payments.get(paymentId);

  if (!payment) {
    return createErrorResponse('Payment not found');
  }

  if (payment.status !== 'completed') {
    return createErrorResponse('Cannot refund non-completed payment');
  }

  // 模拟退款处理
  await delay(1000);

  payment.status = 'refunded';

  const orderResponse = getOrderById(payment.orderId);
  if (orderResponse.success && orderResponse.data) {
    updateOrderStatus(payment.orderId, 'cancelled');
  }

  return createApiResponse(payment);
}

export function getPaymentStatus(paymentId: string): PaymentStatus | null {
  const payment = payments.get(paymentId);
  return payment?.status || null;
}

export function getTotalPaymentAmount(orderId: string): number {
  const orderPayments = Array.from(payments.values()).filter(
    p => p.orderId === orderId && p.status === 'completed'
  );
  return orderPayments.reduce((sum, p) => sum + p.amount, 0);
}

export function getPaymentsByStatus(status: PaymentStatus): ApiResponse<Payment[]> {
  const statusPayments = Array.from(payments.values()).filter(p => p.status === status);
  return createApiResponse(statusPayments);
}

export async function retryFailedPayment(paymentId: string): Promise<ApiResponse<Payment>> {
  const payment = payments.get(paymentId);

  if (!payment) {
    return createErrorResponse('Payment not found');
  }

  if (payment.status !== 'failed') {
    return createErrorResponse('Payment is not in failed status');
  }

  payment.status = 'pending';

  const success = await simulatePaymentGateway(payment.method, payment.amount);

  if (success) {
    payment.status = 'completed';
    payment.transactionId = generateId();
    updateOrderStatus(payment.orderId, 'paid');
  } else {
    payment.status = 'failed';
  }

  return createApiResponse(payment);
}
