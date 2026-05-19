// Shopping cart service — handles cart logic and calls API
import type { CartItem, ProductOption, ApiResponse } from "../types/models";
import { apiClient } from "../api/client";
import { formatCurrency } from "../utils/format";
import { getCurrentSession } from "./auth";

export interface CartState {
  items: CartItem[];
  itemCount: number;
  subtotal: number;
}

export interface AddToCartPayload {
  productId: string;
  sku: string;
  name: string;
  price: number;
  quantity: number;
  selectedOptions: ProductOption[];
  thumbnailUrl: string;
}

let cachedCart: CartState = { items: [], itemCount: 0, subtotal: 0 };

export async function loadCartFromServer(): Promise<CartState> {
  const session = getCurrentSession();
  if (!session) {
    cachedCart = { items: [], itemCount: 0, subtotal: 0 };
    return cachedCart;
  }

  const response: ApiResponse<CartItem[]> = await apiClient.fetchCartItems(
    session.user.id
  );

  if (response.data) {
    cachedCart = computeCartState(response.data);
  }
  return cachedCart;
}

export async function addItemToCart(payload: AddToCartPayload): Promise<CartState> {
  const session = getCurrentSession();
  if (!session) throw new Error("Not authenticated");

  const cartItem: CartItem = {
    ...payload,
    addedAt: Date.now(),
  };

  await apiClient.addToCart(session.user.id, payload.productId, payload.quantity);
  cachedCart.items.push(cartItem);
  cachedCart = computeCartState(cachedCart.items);
  return cachedCart;
}

export async function removeItemFromCart(productId: string): Promise<CartState> {
  cachedCart.items = cachedCart.items.filter((item) => item.productId !== productId);
  cachedCart = computeCartState(cachedCart.items);
  return cachedCart;
}

export function getCartState(): CartState {
  return cachedCart;
}

export function getCartSubtotalFormatted(): string {
  return formatCurrency(cachedCart.subtotal, "CNY");
}

function computeCartState(items: CartItem[]): CartState {
  const itemCount = items.reduce((sum, item) => sum + item.quantity, 0);
  const subtotal = items.reduce(
    (sum, item) => {
      const optionExtra = item.selectedOptions.reduce(
        (oSum, opt) => oSum + opt.priceModifier,
        0
      );
      return sum + (item.price + optionExtra) * item.quantity;
    },
    0
  );
  return { items, itemCount, subtotal };
}

export { formatCurrency };
