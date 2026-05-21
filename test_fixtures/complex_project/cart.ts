// 购物车服务
import { Cart, CartItem, Product, ApiResponse } from './types';
import { createApiResponse, createErrorResponse, calculateDiscount } from './utils';
import { getProductById } from './product';
import { getUserById } from './auth';

// 模拟购物车数据库
const carts: Map<string, Cart> = new Map();

export function getCart(userId: string): ApiResponse<Cart> {
  let cart = carts.get(userId);

  if (!cart) {
    cart = {
      userId,
      items: [],
      totalAmount: 0,
    };
    carts.set(userId, cart);
  }

  return createApiResponse(cart);
}

export function addToCart(userId: string, productId: string, quantity: number): ApiResponse<Cart> {
  const user = getUserById(userId);
  if (!user) {
    return createErrorResponse('User not found');
  }

  const productResponse = getProductById(productId);
  if (!productResponse.success || !productResponse.data) {
    return createErrorResponse('Product not found');
  }

  const product = productResponse.data;

  if (product.stock < quantity) {
    return createErrorResponse('Insufficient stock');
  }

  let cart = carts.get(userId);
  if (!cart) {
    cart = {
      userId,
      items: [],
      totalAmount: 0,
    };
  }

  // 检查商品是否已在购物车中
  const existingItem = cart.items.find(item => item.productId === productId);

  if (existingItem) {
    existingItem.quantity += quantity;
  } else {
    const cartItem: CartItem = {
      productId,
      quantity,
      price: product.price,
      product,
    };
    cart.items.push(cartItem);
  }

  cart.totalAmount = calculateCartTotal(cart);
  carts.set(userId, cart);

  return createApiResponse(cart);
}

export function removeFromCart(userId: string, productId: string): ApiResponse<Cart> {
  const cart = carts.get(userId);

  if (!cart) {
    return createErrorResponse('Cart not found');
  }

  cart.items = cart.items.filter(item => item.productId !== productId);
  cart.totalAmount = calculateCartTotal(cart);
  carts.set(userId, cart);

  return createApiResponse(cart);
}

export function updateCartItemQuantity(userId: string, productId: string, quantity: number): ApiResponse<Cart> {
  const cart = carts.get(userId);

  if (!cart) {
    return createErrorResponse('Cart not found');
  }

  const item = cart.items.find(item => item.productId === productId);

  if (!item) {
    return createErrorResponse('Item not found in cart');
  }

  if (quantity <= 0) {
    return removeFromCart(userId, productId);
  }

  const productResponse = getProductById(productId);
  if (!productResponse.success || !productResponse.data) {
    return createErrorResponse('Product not found');
  }

  if (productResponse.data.stock < quantity) {
    return createErrorResponse('Insufficient stock');
  }

  item.quantity = quantity;
  cart.totalAmount = calculateCartTotal(cart);
  carts.set(userId, cart);

  return createApiResponse(cart);
}

export function applyDiscount(userId: string, discountCode: string): ApiResponse<Cart> {
  const cart = carts.get(userId);

  if (!cart) {
    return createErrorResponse('Cart not found');
  }

  // 简化的折扣验证
  const discounts: Record<string, { percentage: number; maxAmount?: number }> = {
    'SAVE10': { percentage: 10 },
    'SAVE20': { percentage: 20, maxAmount: 50 },
    'VIP30': { percentage: 30, maxAmount: 100 },
  };

  const discount = discounts[discountCode];

  if (!discount) {
    return createErrorResponse('Invalid discount code');
  }

  cart.discount = {
    code: discountCode,
    percentage: discount.percentage,
    maxAmount: discount.maxAmount,
  };

  cart.totalAmount = calculateCartTotal(cart);
  carts.set(userId, cart);

  return createApiResponse(cart);
}

export function clearCart(userId: string): ApiResponse<void> {
  carts.delete(userId);
  return createApiResponse(undefined);
}

function calculateCartTotal(cart: Cart): number {
  let total = cart.items.reduce((sum, item) => sum + item.price * item.quantity, 0);

  if (cart.discount) {
    const discountAmount = calculateDiscount(total, cart.discount.percentage, cart.discount.maxAmount);
    total -= discountAmount;
  }

  return Math.max(0, total);
}

export function getCartItemCount(userId: string): number {
  const cart = carts.get(userId);
  return cart ? cart.items.reduce((sum, item) => sum + item.quantity, 0) : 0;
}

export function validateCartStock(userId: string): ApiResponse<boolean> {
  const cart = carts.get(userId);

  if (!cart) {
    return createErrorResponse('Cart not found');
  }

  for (const item of cart.items) {
    const productResponse = getProductById(item.productId);
    if (!productResponse.success || !productResponse.data) {
      return createErrorResponse(`Product ${item.productId} not found`);
    }

    if (productResponse.data.stock < item.quantity) {
      return createErrorResponse(`Insufficient stock for ${productResponse.data.name}`);
    }
  }

  return createApiResponse(true);
}
