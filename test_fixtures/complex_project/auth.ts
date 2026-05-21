// 用户认证服务
import { User, UserRole, ApiResponse } from './types';
import { generateId, validateEmail, createApiResponse, createErrorResponse } from './utils';
import { sendNotification } from './notification';
import { getUserOrders } from './order';

interface LoginCredentials {
  email: string;
  password: string;
}

interface RegisterData {
  email: string;
  password: string;
  name: string;
  role?: UserRole;
}

// 模拟用户数据库
const users: Map<string, User> = new Map();
const sessions: Map<string, string> = new Map(); // sessionId -> userId

export function register(data: RegisterData): ApiResponse<User> {
  if (!validateEmail(data.email)) {
    return createErrorResponse('Invalid email format');
  }

  // 检查邮箱是否已存在
  const existingUser = Array.from(users.values()).find(u => u.email === data.email);
  if (existingUser) {
    return createErrorResponse('Email already registered');
  }

  const user: User = {
    id: generateId(),
    email: data.email,
    name: data.name,
    role: data.role || 'customer',
    createdAt: new Date(),
  };

  users.set(user.id, user);

  // 发送欢迎通知
  sendNotification(user.id, 'Welcome to our platform!', 'promotion');

  return createApiResponse(user);
}

export function login(credentials: LoginCredentials): ApiResponse<{ user: User; sessionId: string }> {
  const user = Array.from(users.values()).find(u => u.email === credentials.email);

  if (!user) {
    return createErrorResponse('User not found');
  }

  // 简化的密码验证（实际应该使用哈希）
  const sessionId = generateId();
  sessions.set(sessionId, user.id);

  return createApiResponse({ user, sessionId });
}

export function logout(sessionId: string): ApiResponse<void> {
  if (!sessions.has(sessionId)) {
    return createErrorResponse('Invalid session');
  }

  sessions.delete(sessionId);
  return createApiResponse(undefined);
}

export function getCurrentUser(sessionId: string): ApiResponse<User> {
  const userId = sessions.get(sessionId);

  if (!userId) {
    return createErrorResponse('Session expired');
  }

  const user = users.get(userId);
  if (!user) {
    return createErrorResponse('User not found');
  }

  return createApiResponse(user);
}

export function getUserById(userId: string): User | undefined {
  return users.get(userId);
}

export function updateUserProfile(userId: string, updates: Partial<User>): ApiResponse<User> {
  const user = users.get(userId);

  if (!user) {
    return createErrorResponse('User not found');
  }

  const updatedUser = { ...user, ...updates, id: user.id };
  users.set(userId, updatedUser);

  return createApiResponse(updatedUser);
}

export function getUserWithOrders(userId: string): ApiResponse<{ user: User; orders: any[] }> {
  const user = users.get(userId);

  if (!user) {
    return createErrorResponse('User not found');
  }

  const orders = getUserOrders(userId);

  return createApiResponse({ user, orders: orders.data || [] });
}

export function isAdmin(userId: string): boolean {
  const user = users.get(userId);
  return user?.role === 'admin';
}

export function isVendor(userId: string): boolean {
  const user = users.get(userId);
  return user?.role === 'vendor';
}
