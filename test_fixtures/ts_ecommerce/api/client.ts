// API client — handles all HTTP requests, imports config and types
import type {
  ApiResponse,
  PaginatedResponse,
  UserProfile,
  CartItem,
  OrderSummary,
  AuthToken,
  ApiError,
} from "../types/models";
import { DEFAULT_CONFIG, type AppConfig } from "../config/app";

export class ApiClient {
  private config: AppConfig;
  private authToken: AuthToken | null = null;
  private requestQueue: Array<() => Promise<void>> = [];
  private isRefreshing = false;

  constructor(configOverride?: Partial<AppConfig>) {
    this.config = { ...DEFAULT_CONFIG, ...configOverride };
  }

  setAuthToken(token: AuthToken): void {
    this.authToken = token;
  }

  async fetchUserProfile(userId: string): Promise<ApiResponse<UserProfile>> {
    return this.request<UserProfile>("GET", `/users/${userId}`);
  }

  async fetchCartItems(userId: string): Promise<ApiResponse<CartItem[]>> {
    return this.request<CartItem[]>("GET", `/users/${userId}/cart`);
  }

  async addToCart(
    userId: string,
    productId: string,
    quantity: number
  ): Promise<ApiResponse<CartItem>> {
    return this.request<CartItem>("POST", `/users/${userId}/cart`, {
      productId,
      quantity,
    });
  }

  async submitOrder(order: OrderSummary): Promise<ApiResponse<OrderSummary>> {
    return this.request<OrderSummary>("POST", "/orders", order);
  }

  async fetchOrderHistory(
    userId: string,
    page: number = 1
  ): Promise<ApiResponse<PaginatedResponse<OrderSummary>>> {
    return this.request<PaginatedResponse<OrderSummary>>(
      "GET",
      `/users/${userId}/orders?page=${page}&pageSize=20`
    );
  }

  private async request<T>(
    method: string,
    path: string,
    body?: unknown
  ): Promise<ApiResponse<T>> {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
    };
    if (this.authToken) {
      headers["Authorization"] = `${this.authToken.tokenType} ${this.authToken.accessToken}`;
    }

    const response = await fetch(`${this.config.apiBaseUrl}${path}`, {
      method,
      headers,
      body: body ? JSON.stringify(body) : undefined,
    });

    if (response.status === 401) {
      return this.retryWithRefresh<T>(method, path, body);
    }

    const json: ApiResponse<T> = await response.json();

    if (json.code >= 400) {
      throw new ApiRequestError(json.code, json.message, (json.data as unknown as ApiError)?.details);
    }

    return json;
  }

  private async retryWithRefresh<T>(
    method: string,
    path: string,
    body?: unknown
  ): Promise<ApiResponse<T>> {
    if (this.isRefreshing) {
      return new Promise((resolve) => {
        this.requestQueue.push(async () => {
          resolve(await this.request<T>(method, path, body));
        });
      });
    }

    this.isRefreshing = true;
    try {
      const newToken = await this.refreshAuthToken();
      this.authToken = newToken;
      // Process queued requests
      while (this.requestQueue.length > 0) {
        const queued = this.requestQueue.shift();
        if (queued) queued();
      }
      return this.request<T>(method, path, body);
    } finally {
      this.isRefreshing = false;
    }
  }

  private async refreshAuthToken(): Promise<AuthToken> {
    const response = await fetch(`${this.config.apiBaseUrl}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refreshToken: this.authToken?.refreshToken }),
    });
    const json: ApiResponse<AuthToken> = await response.json();
    if (!json.data) throw new Error("Token refresh failed");
    return json.data;
  }
}

export class ApiRequestError extends Error {
  code: number;
  details?: Record<string, string>;
  constructor(code: number, message: string, details?: Record<string, string>) {
    super(message);
    this.code = code;
    this.details = details;
    this.name = "ApiRequestError";
  }
}

export const apiClient = new ApiClient();
