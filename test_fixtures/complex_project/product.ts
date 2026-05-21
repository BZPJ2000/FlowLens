// 产品管理服务
import { Product, ApiResponse } from './types';
import { generateId, createApiResponse, createErrorResponse, chunk } from './utils';
import { isVendor, isAdmin } from './auth';
import { notifyPriceChange, notifyStockAlert } from './notification';

// 模拟产品数据库
const products: Map<string, Product> = new Map();
const categories: Set<string> = new Set(['Electronics', 'Clothing', 'Books', 'Home', 'Sports']);

export function createProduct(vendorId: string, productData: Omit<Product, 'id' | 'vendorId'>): ApiResponse<Product> {
  if (!isVendor(vendorId) && !isAdmin(vendorId)) {
    return createErrorResponse('Only vendors can create products');
  }

  if (!categories.has(productData.category)) {
    return createErrorResponse('Invalid category');
  }

  const product: Product = {
    id: generateId(),
    vendorId,
    ...productData,
  };

  products.set(product.id, product);

  return createApiResponse(product);
}

export function getProductById(productId: string): ApiResponse<Product> {
  const product = products.get(productId);

  if (!product) {
    return createErrorResponse('Product not found');
  }

  return createApiResponse(product);
}

export function getAllProducts(): ApiResponse<Product[]> {
  return createApiResponse(Array.from(products.values()));
}

export function getProductsByCategory(category: string): ApiResponse<Product[]> {
  const categoryProducts = Array.from(products.values()).filter(p => p.category === category);
  return createApiResponse(categoryProducts);
}

export function getProductsByVendor(vendorId: string): ApiResponse<Product[]> {
  const vendorProducts = Array.from(products.values()).filter(p => p.vendorId === vendorId);
  return createApiResponse(vendorProducts);
}

export function searchProducts(query: string): ApiResponse<Product[]> {
  const lowerQuery = query.toLowerCase();
  const results = Array.from(products.values()).filter(p =>
    p.name.toLowerCase().includes(lowerQuery) ||
    p.tags.some(tag => tag.toLowerCase().includes(lowerQuery))
  );
  return createApiResponse(results);
}

export function updateProduct(productId: string, vendorId: string, updates: Partial<Product>): ApiResponse<Product> {
  const product = products.get(productId);

  if (!product) {
    return createErrorResponse('Product not found');
  }

  if (product.vendorId !== vendorId && !isAdmin(vendorId)) {
    return createErrorResponse('Unauthorized');
  }

  // 检测价格变化
  if (updates.price && updates.price !== product.price) {
    notifyPriceChange(productId, product.price, updates.price);
  }

  const updatedProduct = { ...product, ...updates, id: product.id, vendorId: product.vendorId };
  products.set(productId, updatedProduct);

  return createApiResponse(updatedProduct);
}

export function updateStock(productId: string, quantity: number): ApiResponse<Product> {
  const product = products.get(productId);

  if (!product) {
    return createErrorResponse('Product not found');
  }

  const newStock = product.stock + quantity;

  if (newStock < 0) {
    return createErrorResponse('Insufficient stock');
  }

  product.stock = newStock;

  // 库存预警
  if (newStock < 10) {
    notifyStockAlert(productId, newStock);
  }

  return createApiResponse(product);
}

export function deleteProduct(productId: string, vendorId: string): ApiResponse<void> {
  const product = products.get(productId);

  if (!product) {
    return createErrorResponse('Product not found');
  }

  if (product.vendorId !== vendorId && !isAdmin(vendorId)) {
    return createErrorResponse('Unauthorized');
  }

  products.delete(productId);
  return createApiResponse(undefined);
}

export function getProductsInBatches(batchSize: number): Product[][] {
  const allProducts = Array.from(products.values());
  return chunk(allProducts, batchSize);
}

export function getAvailableCategories(): string[] {
  return Array.from(categories);
}
