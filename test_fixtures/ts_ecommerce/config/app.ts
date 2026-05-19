// Application configuration — imported by services and API layer

export interface AppConfig {
  apiBaseUrl: string;
  wsEndpoint: string;
  authProvider: "google" | "github" | "wechat" | "custom";
  sessionTimeoutMs: number;
  maxCartItems: number;
  maxRetryAttempts: number;
  uploadMaxSizeMb: number;
  featureFlags: FeatureFlags;
  paymentGateways: PaymentGatewayConfig[];
}

export interface FeatureFlags {
  enableNewCheckout: boolean;
  enableLiveChat: boolean;
  enableRecommendations: boolean;
  enableDarkMode: boolean;
  enableAnalytics: boolean;
}

export interface PaymentGatewayConfig {
  provider: "stripe" | "wechat_pay" | "alipay" | "paypal";
  merchantId: string;
  apiKey: string;
  sandbox: boolean;
  supportedCurrencies: string[];
}

export function loadAppConfig(): AppConfig {
  return {
    apiBaseUrl: process.env.NEXT_PUBLIC_API_URL || "/api",
    wsEndpoint: process.env.NEXT_PUBLIC_WS_URL || "wss://api.example.com/ws",
    authProvider: "custom",
    sessionTimeoutMs: 3600000,
    maxCartItems: 99,
    maxRetryAttempts: 3,
    uploadMaxSizeMb: 10,
    featureFlags: {
      enableNewCheckout: true,
      enableLiveChat: false,
      enableRecommendations: true,
      enableDarkMode: true,
      enableAnalytics: true,
    },
    paymentGateways: [
      {
        provider: "wechat_pay",
        merchantId: "wx_merchant_001",
        apiKey: "sk_live_wx_xxxx",
        sandbox: false,
        supportedCurrencies: ["CNY"],
      },
      {
        provider: "alipay",
        merchantId: "ali_merchant_002",
        apiKey: "sk_live_ali_xxxx",
        sandbox: false,
        supportedCurrencies: ["CNY"],
      },
    ],
  };
}

export const DEFAULT_CONFIG: AppConfig = loadAppConfig();
