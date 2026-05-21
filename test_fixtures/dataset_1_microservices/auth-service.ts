// Authentication Service
import { hashPassword, comparePassword } from './crypto-utils';
import { generateToken, verifyToken } from './jwt-utils';
import { getUserByEmail, createUser } from './database';
import { logAuthEvent } from './logging-service';
import { sendEmail } from './email-service';

export interface User {
  id: string;
  email: string;
  passwordHash: string;
  role: string;
  createdAt: Date;
}

export interface AuthToken {
  token: string;
  expiresAt: Date;
  userId: string;
}

export async function authenticateUser(token: string): Promise<User | null> {
  try {
    const payload = await verifyToken(token);
    if (!payload) return null;

    const user = await getUserByEmail(payload.email);
    logAuthEvent('token_verified', user?.id || 'unknown');
    return user;
  } catch (error) {
    logAuthEvent('token_verification_failed', 'unknown');
    return null;
  }
}

export async function login(email: string, password: string): Promise<AuthToken | null> {
  const user = await getUserByEmail(email);
  if (!user) {
    logAuthEvent('login_failed', email);
    return null;
  }

  const valid = await comparePassword(password, user.passwordHash);
  if (!valid) {
    logAuthEvent('invalid_password', user.id);
    return null;
  }

  const token = await generateToken({ userId: user.id, email: user.email, role: user.role });
  logAuthEvent('login_success', user.id);

  return {
    token,
    expiresAt: new Date(Date.now() + 24 * 60 * 60 * 1000),
    userId: user.id,
  };
}

export async function register(email: string, password: string, role: string = 'user'): Promise<User | null> {
  const existing = await getUserByEmail(email);
  if (existing) {
    logAuthEvent('registration_failed_duplicate', email);
    return null;
  }

  const passwordHash = await hashPassword(password);
  const user = await createUser({ email, passwordHash, role });

  logAuthEvent('registration_success', user.id);
  await sendEmail(email, 'Welcome!', 'Thanks for registering');

  return user;
}

export async function validateToken(token: string): Promise<boolean> {
  const payload = await verifyToken(token);
  return payload !== null;
}

export async function refreshToken(oldToken: string): Promise<AuthToken | null> {
  const user = await authenticateUser(oldToken);
  if (!user) return null;

  const token = await generateToken({ userId: user.id, email: user.email, role: user.role });
  return {
    token,
    expiresAt: new Date(Date.now() + 24 * 60 * 60 * 1000),
    userId: user.id,
  };
}

export async function logout(token: string): Promise<void> {
  const user = await authenticateUser(token);
  if (user) {
    logAuthEvent('logout', user.id);
  }
}
