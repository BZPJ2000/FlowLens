// API Gateway - 微服务入口
import { Request, Response, NextFunction } from 'express';
import { authenticateUser, validateToken } from './auth-service';
import { getUserProfile, updateUserProfile } from './user-service';
import { getProducts, createOrder } from './order-service';
import { processPayment, refundPayment } from './payment-service';
import { sendNotification } from './notification-service';
import { logRequest, logError } from './logging-service';
import { cacheGet, cacheSet } from './cache-service';
import { rateLimitCheck } from './rate-limiter';

export interface GatewayConfig {
  port: number;
  timeout: number;
  maxRetries: number;
  services: ServiceEndpoint[];
}

export interface ServiceEndpoint {
  name: string;
  url: string;
  healthCheck: string;
}

export async function handleRequest(req: Request, res: Response, next: NextFunction): Promise<void> {
  const requestId = generateRequestId();
  logRequest(requestId, req.method, req.path);

  try {
    // Rate limiting
    const allowed = await rateLimitCheck(req.ip);
    if (!allowed) {
      res.status(429).json({ error: 'Too many requests' });
      return;
    }

    // Authentication
    const token = req.headers.authorization?.split(' ')[1];
    if (!token) {
      res.status(401).json({ error: 'No token provided' });
      return;
    }

    const user = await authenticateUser(token);
    if (!user) {
      res.status(401).json({ error: 'Invalid token' });
      return;
    }

    // Route to appropriate service
    await routeRequest(req, res, user);
  } catch (error) {
    logError(requestId, error as Error);
    res.status(500).json({ error: 'Internal server error' });
  }
}

async function routeRequest(req: Request, res: Response, user: any): Promise<void> {
  const path = req.path;

  if (path.startsWith('/api/users')) {
    await handleUserRequest(req, res, user);
  } else if (path.startsWith('/api/products')) {
    await handleProductRequest(req, res, user);
  } else if (path.startsWith('/api/orders')) {
    await handleOrderRequest(req, res, user);
  } else if (path.startsWith('/api/payments')) {
    await handlePaymentRequest(req, res, user);
  } else {
    res.status(404).json({ error: 'Not found' });
  }
}

async function handleUserRequest(req: Request, res: Response, user: any): Promise<void> {
  const cached = await cacheGet(`user:${user.id}`);
  if (cached) {
    res.json(cached);
    return;
  }

  const profile = await getUserProfile(user.id);
  await cacheSet(`user:${user.id}`, profile, 300);
  res.json(profile);
}

async function handleProductRequest(req: Request, res: Response, user: any): Promise<void> {
  const products = await getProducts();
  res.json(products);
}

async function handleOrderRequest(req: Request, res: Response, user: any): Promise<void> {
  if (req.method === 'POST') {
    const order = await createOrder(user.id, req.body);
    await sendNotification(user.id, `Order ${order.id} created`);
    res.json(order);
  }
}

async function handlePaymentRequest(req: Request, res: Response, user: any): Promise<void> {
  if (req.method === 'POST') {
    const payment = await processPayment(req.body);
    res.json(payment);
  }
}

function generateRequestId(): string {
  return `req_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
}

export function startGateway(config: GatewayConfig): void {
  console.log(`API Gateway starting on port ${config.port}`);
}
