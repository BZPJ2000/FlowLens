// User Service
import { User } from './auth-service';
import { getUserById, updateUser, deleteUser } from './database';
import { cacheGet, cacheSet, cacheDelete } from './cache-service';
import { publishEvent } from './event-bus';
import { validateEmail, validatePhone } from './validators';

export interface UserProfile {
  id: string;
  email: string;
  name: string;
  phone?: string;
  address?: Address;
  preferences: UserPreferences;
}

export interface Address {
  street: string;
  city: string;
  state: string;
  zipCode: string;
  country: string;
}

export interface UserPreferences {
  language: string;
  timezone: string;
  notifications: boolean;
  theme: 'light' | 'dark';
}

export async function getUserProfile(userId: string): Promise<UserProfile | null> {
  const cached = await cacheGet(`profile:${userId}`);
  if (cached) return cached as UserProfile;

  const user = await getUserById(userId);
  if (!user) return null;

  const profile: UserProfile = {
    id: user.id,
    email: user.email,
    name: user.name || '',
    phone: user.phone,
    address: user.address,
    preferences: user.preferences || getDefaultPreferences(),
  };

  await cacheSet(`profile:${userId}`, profile, 600);
  return profile;
}

export async function updateUserProfile(userId: string, updates: Partial<UserProfile>): Promise<UserProfile | null> {
  if (updates.email && !validateEmail(updates.email)) {
    throw new Error('Invalid email');
  }

  if (updates.phone && !validatePhone(updates.phone)) {
    throw new Error('Invalid phone');
  }

  const updated = await updateUser(userId, updates);
  if (!updated) return null;

  await cacheDelete(`profile:${userId}`);
  await publishEvent('user.updated', { userId, updates });

  return getUserProfile(userId);
}

export async function deleteUserProfile(userId: string): Promise<boolean> {
  const deleted = await deleteUser(userId);
  if (deleted) {
    await cacheDelete(`profile:${userId}`);
    await publishEvent('user.deleted', { userId });
  }
  return deleted;
}

function getDefaultPreferences(): UserPreferences {
  return {
    language: 'en',
    timezone: 'UTC',
    notifications: true,
    theme: 'dark',
  };
}

export async function searchUsers(query: string): Promise<UserProfile[]> {
  // Simplified search
  return [];
}

export async function getUsersByRole(role: string): Promise<UserProfile[]> {
  return [];
}
