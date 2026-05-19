// Zustand cart store — state management layer consumed by UI pages
import type { CartItem, ProductOption, OrderSummary, ShippingInfo } from "../types/models";
import {
  loadCartFromServer,
  addItemToCart,
  removeItemFromCart,
  getCartState,
  getCartSubtotalFormatted,
  type CartState,
  type AddToCartPayload,
} from "../services/cart";
import { formatOrderNumber, formatDate } from "../utils/format";
import { isAuthenticated } from "../services/auth";

interface CheckoutStep {
  step: "cart" | "shipping" | "payment" | "confirmation";
  orderSummary: Partial<OrderSummary>;
  shippingAddress: Partial<ShippingInfo>;
}

interface CartStore extends CartState {
  isLoading: boolean;
  isCheckingOut: boolean;
  checkoutStep: CheckoutStep;
  subtotalFormatted: string;
  orderNumbers: string[];

  // Actions
  initialize: () => Promise<void>;
  addItem: (payload: AddToCartPayload) => Promise<void>;
  removeItem: (productId: string) => Promise<void>;
  proceedToCheckout: () => Promise<void>;
  setShippingAddress: (address: Partial<ShippingInfo>) => void;
  confirmOrder: () => Promise<string>;
  resetCheckout: () => void;
}

// Simulated store (not using zustand for test fixture simplicity)
const defaultCart: CartState = { items: [], itemCount: 0, subtotal: 0 };

export const useCartStore: CartStore = {
  items: defaultCart.items,
  itemCount: defaultCart.itemCount,
  subtotal: defaultCart.subtotal,
  isLoading: false,
  isCheckingOut: false,
  checkoutStep: { step: "cart", orderSummary: {}, shippingAddress: {} },
  subtotalFormatted: "¥0.00",
  orderNumbers: [],

  async initialize() {
    this.isLoading = true;
    const state = await loadCartFromServer();
    Object.assign(this, state);
    this.subtotalFormatted = getCartSubtotalFormatted();
    this.isLoading = false;
  },

  async addItem(payload: AddToCartPayload) {
    const state = await addItemToCart(payload);
    Object.assign(this, state);
    this.subtotalFormatted = getCartSubtotalFormatted();
  },

  async removeItem(productId: string) {
    const state = await removeItemFromCart(productId);
    Object.assign(this, state);
    this.subtotalFormatted = getCartSubtotalFormatted();
  },

  async proceedToCheckout() {
    if (!isAuthenticated()) throw new Error("Please login first");
    this.isCheckingOut = true;
    this.checkoutStep.step = "shipping";
  },

  setShippingAddress(address: Partial<ShippingInfo>) {
    this.checkoutStep.shippingAddress = {
      ...this.checkoutStep.shippingAddress,
      ...address,
    };
  },

  async confirmOrder(): Promise<string> {
    const mockOrderId = `ord_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
    const formattedOrderNumber = formatOrderNumber(mockOrderId);
    this.orderNumbers.push(formattedOrderNumber);
    this.checkoutStep.step = "confirmation";
    this.isCheckingOut = false;
    return formattedOrderNumber;
  },

  resetCheckout() {
    this.checkoutStep = { step: "cart", orderSummary: {}, shippingAddress: {} };
    this.isCheckingOut = false;
  },
};
