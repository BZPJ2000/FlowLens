// 主应用入口 - 整合所有模块
import { register, login, logout, getCurrentUser, getUserWithOrders } from './auth';
import { createProduct, getProductById, searchProducts, updateStock } from './product';
import { addToCart, getCart, applyDiscount, updateCartItemQuantity } from './cart';
import { createOrder, getOrderById, processOrderPayment, cancelOrder } from './order';
import { processPayment, refundPayment, getPaymentStatus } from './payment';
import { getUserNotifications, getUnreadNotifications, markAllAsRead } from './notification';
import { formatCurrency, formatDate, validateEmail } from './utils';
import { User, Product, Order, ApiResponse } from './types';

// 应用配置
interface AppConfig {
  apiUrl: string;
  environment: 'development' | 'production';
  features: {
    enablePayments: boolean;
    enableNotifications: boolean;
    enableDiscounts: boolean;
  };
}

const config: AppConfig = {
  apiUrl: 'https://api.example.com',
  environment: 'development',
  features: {
    enablePayments: true,
    enableNotifications: true,
    enableDiscounts: true,
  },
};

// 应用状态管理
class AppState {
  private currentUser: User | null = null;
  private sessionId: string | null = null;

  setUser(user: User, sessionId: string): void {
    this.currentUser = user;
    this.sessionId = sessionId;
  }

  getUser(): User | null {
    return this.currentUser;
  }

  getSessionId(): string | null {
    return this.sessionId;
  }

  clearUser(): void {
    this.currentUser = null;
    this.sessionId = null;
  }

  isAuthenticated(): boolean {
    return this.currentUser !== null && this.sessionId !== null;
  }
}

const appState = new AppState();

// 用户流程：注册 -> 登录 -> 浏览产品 -> 加入购物车 -> 下单 -> 支付
export async function completeUserJourney() {
  console.log('=== Starting Complete User Journey ===\n');

  // 1. 用户注册
  console.log('Step 1: User Registration');
  const registerResult = register({
    email: 'john.doe@example.com',
    password: 'securePassword123',
    name: 'John Doe',
    role: 'customer',
  });

  if (!registerResult.success || !registerResult.data) {
    console.error('Registration failed:', registerResult.error);
    return;
  }

  const user = registerResult.data;
  console.log(`✓ User registered: ${user.name} (${user.email})\n`);

  // 2. 用户登录
  console.log('Step 2: User Login');
  const loginResult = login({
    email: 'john.doe@example.com',
    password: 'securePassword123',
  });

  if (!loginResult.success || !loginResult.data) {
    console.error('Login failed:', loginResult.error);
    return;
  }

  appState.setUser(loginResult.data.user, loginResult.data.sessionId);
  console.log(`✓ User logged in with session: ${loginResult.data.sessionId}\n`);

  // 3. 创建一些产品（作为供应商）
  console.log('Step 3: Creating Products');
  const vendorRegister = register({
    email: 'vendor@example.com',
    password: 'vendorPass123',
    name: 'Tech Vendor',
    role: 'vendor',
  });

  if (!vendorRegister.success || !vendorRegister.data) {
    console.error('Vendor registration failed');
    return;
  }

  const vendor = vendorRegister.data;

  const product1 = createProduct(vendor.id, {
    name: 'Wireless Headphones',
    price: 99.99,
    stock: 50,
    category: 'Electronics',
    tags: ['audio', 'wireless', 'bluetooth'],
  });

  const product2 = createProduct(vendor.id, {
    name: 'Smart Watch',
    price: 299.99,
    stock: 30,
    category: 'Electronics',
    tags: ['wearable', 'fitness', 'smart'],
  });

  console.log(`✓ Created products: ${product1.data?.name}, ${product2.data?.name}\n`);

  // 4. 浏览和搜索产品
  console.log('Step 4: Browsing Products');
  const searchResult = searchProducts('wireless');
  console.log(`✓ Found ${searchResult.data?.length} products matching "wireless"\n`);

  // 5. 添加到购物车
  console.log('Step 5: Adding to Cart');
  if (product1.data && product2.data) {
    await addToCart(user.id, product1.data.id, 2);
    await addToCart(user.id, product2.data.id, 1);
  }

  const cartResult = getCart(user.id);
  console.log(`✓ Cart total: ${formatCurrency(cartResult.data?.totalAmount || 0)}\n`);

  // 6. 应用折扣
  if (config.features.enableDiscounts) {
    console.log('Step 6: Applying Discount');
    const discountResult = applyDiscount(user.id, 'SAVE10');
    console.log(`✓ Discount applied: ${formatCurrency(discountResult.data?.totalAmount || 0)}\n`);
  }

  // 7. 创建订单
  console.log('Step 7: Creating Order');
  const orderResult = createOrder(user.id, {
    street: '123 Main St',
    city: 'San Francisco',
    state: 'CA',
    zipCode: '94102',
    country: 'US',
  });

  if (!orderResult.success || !orderResult.data) {
    console.error('Order creation failed:', orderResult.error);
    return;
  }

  const order = orderResult.data;
  console.log(`✓ Order created: ${order.id}\n`);

  // 8. 处理支付
  if (config.features.enablePayments) {
    console.log('Step 8: Processing Payment');
    const paymentResult = await processOrderPayment(order.id, 'credit_card');

    if (paymentResult.success) {
      console.log(`✓ Payment completed for order ${order.id}\n`);
    } else {
      console.error('Payment failed:', paymentResult.error);
    }
  }

  // 9. 查看通知
  if (config.features.enableNotifications) {
    console.log('Step 9: Checking Notifications');
    const notificationsResult = getUserNotifications(user.id);
    console.log(`✓ User has ${notificationsResult.data?.length} notifications\n`);
  }

  // 10. 查看用户订单历史
  console.log('Step 10: Viewing Order History');
  const userWithOrders = getUserWithOrders(user.id);
  console.log(`✓ User has ${userWithOrders.data?.orders.length} orders\n`);

  console.log('=== User Journey Completed Successfully ===');
}

// 管理员流程：查看所有订单、管理产品、处理退款
export async function adminWorkflow() {
  console.log('=== Admin Workflow ===\n');

  // 创建管理员账户
  const adminRegister = register({
    email: 'admin@example.com',
    password: 'adminPass123',
    name: 'Admin User',
    role: 'admin',
  });

  if (!adminRegister.success || !adminRegister.data) {
    console.error('Admin registration failed');
    return;
  }

  const admin = adminRegister.data;
  console.log(`✓ Admin account created: ${admin.name}\n`);

  // 管理员可以执行的操作...
  console.log('Admin can now manage products, view all orders, and process refunds');
}

// 导出主要功能
export {
  // Auth
  register,
  login,
  logout,
  getCurrentUser,
  getUserWithOrders,

  // Products
  createProduct,
  getProductById,
  searchProducts,
  updateStock,

  // Cart
  addToCart,
  getCart,
  applyDiscount,
  updateCartItemQuantity,

  // Orders
  createOrder,
  getOrderById,
  processOrderPayment,
  cancelOrder,

  // Payments
  processPayment,
  refundPayment,
  getPaymentStatus,

  // Notifications
  getUserNotifications,
  getUnreadNotifications,
  markAllAsRead,

  // Utils
  formatCurrency,
  formatDate,
  validateEmail,

  // App
  appState,
  config,
  completeUserJourney,
  adminWorkflow,
};
