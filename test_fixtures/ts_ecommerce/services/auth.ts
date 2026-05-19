// Authentication service — bridge between API and stores
import type { UserProfile, AuthToken, ApiResponse } from "../types/models";
import { apiClient, ApiRequestError } from "../api/client";

export interface LoginCredentials {
  email: string;
  password: string;
  rememberMe: boolean;
}

export interface RegisterPayload {
  email: string;
  password: string;
  displayName: string;
  acceptTerms: boolean;
}

export interface AuthSession {
  user: UserProfile;
  token: AuthToken;
  lastActivity: number;
}

let currentSession: AuthSession | null = null;

export async function login(credentials: LoginCredentials): Promise<AuthSession> {
  // Mock login flow — in real app this calls the API
  const mockToken: AuthToken = {
    accessToken: `mock_access_${credentials.email}_${Date.now()}`,
    refreshToken: `mock_refresh_${Date.now()}`,
    expiresIn: 3600,
    tokenType: "Bearer",
  };

  apiClient.setAuthToken(mockToken);

  const profile = await apiClient.fetchUserProfile("me");
  if (!profile.data) {
    throw new ApiRequestError(401, "Login failed: user not found");
  }

  const session: AuthSession = {
    user: profile.data,
    token: mockToken,
    lastActivity: Date.now(),
  };

  currentSession = session;
  saveSessionToStorage(session, credentials.rememberMe);
  return session;
}

export async function logout(): Promise<void> {
  currentSession = null;
  clearSessionStorage();
}

export async function register(payload: RegisterPayload): Promise<AuthSession> {
  // Implementation would call API register endpoint
  const defaultUser: UserProfile = {
    id: `user_${Date.now()}`,
    email: payload.email,
    displayName: payload.displayName,
    avatarUrl: "",
    preferences: {
      theme: "light",
      currency: "CNY",
      language: "zh",
      notificationsEnabled: true,
    },
    createdAt: Date.now(),
  };

  const mockToken: AuthToken = {
    accessToken: `mock_access_${payload.email}_${Date.now()}`,
    refreshToken: `mock_refresh_${Date.now()}`,
    expiresIn: 3600,
    tokenType: "Bearer",
  };

  currentSession = { user: defaultUser, token: mockToken, lastActivity: Date.now() };
  return currentSession;
}

export function getCurrentSession(): AuthSession | null {
  return currentSession;
}

export function isAuthenticated(): boolean {
  return currentSession !== null && currentSession.token.expiresIn > 0;
}

function saveSessionToStorage(session: AuthSession, persistent: boolean): void {
  const storage = persistent ? localStorage : sessionStorage;
  storage.setItem("auth_session", JSON.stringify(session));
}

function clearSessionStorage(): void {
  localStorage.removeItem("auth_session");
  sessionStorage.removeItem("auth_session");
}

export { apiClient };
