// Payment Service
import { getOrderById } from './order-service';
import { publishEvent } from './event-bus';
import { logPayment } from './logging-service';

export interface Payment {
  id: string;
  orderId: string;
  amount: number;
  method: PaymentMethod;
  status: PaymentStatus;
  transactionId?: string;
  createdAt: Date;
}

export type PaymentMethod = 'credit_card' | 'debit_card' | 'paypal' | 'stripe' | 'bank_transfer';
export type PaymentStatus = 'pending' | 'processing' | 'completed' | 'failed' | 'refunded';

export async function processPayment(data: { orderId: string; amount: number; method: PaymentMethod }): Promise<Payment> {
  const payment: Payment = {
    id: generatePaymentId(),
    orderId: data.orderId,
    amount: data.amount,
    method: data.method,
    status: 'processing',
    createdAt: new Date(),
  };

  logPayment('payment_initiated', payment.id);

  try {
    const result = await callPaymentGateway(payment);
    payment.status = result.success ? 'completed' : 'failed';
    payment.transactionId = result.transactionId;

    await publishEvent('payment.processed', { paymentId: payment.id, status: payment.status });
    logPayment('payment_completed', payment.id);
  } catch (error) {
    payment.status = 'failed';
    logPayment('payment_failed', payment.id);
  }

  return payment;
}

export async function refundPayment(paymentId: string): Promise<Payment> {
  const payment = await getPaymentById(paymentId);
  if (!payment) throw new Error('Payment not found');

  if (payment.status !== 'completed') {
    throw new Error('Cannot refund non-completed payment');
  }

  const refundResult = await callRefundGateway(payment);
  payment.status = 'refunded';

  await publishEvent('payment.refunded', { paymentId });
  logPayment('payment_refunded', paymentId);

  return payment;
}

async function callPaymentGateway(payment: Payment): Promise<{ success: boolean; transactionId: string }> {
  // Simulate payment gateway call
  await delay(1000);
  return {
    success: Math.random() > 0.1,
    transactionId: `TXN-${Date.now()}`,
  };
}

async function callRefundGateway(payment: Payment): Promise<boolean> {
  await delay(500);
  return true;
}

function generatePaymentId(): string {
  return `PAY-${Date.now()}-${Math.random().toString(36).substr(2, 6).toUpperCase()}`;
}

async function getPaymentById(id: string): Promise<Payment | null> {
  return null;
}

function delay(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms));
}
