# Complex E-commerce Test Project

这是一个用于测试 PoltAIshow 数据流可视化的复杂 TypeScript 项目。

## 项目结构

```
complex_project/
├── types.ts           # 核心类型定义（User, Product, Order, Payment 等）
├── utils.ts           # 工具函数（格式化、验证、API 响应等）
├── auth.ts            # 用户认证服务（注册、登录、权限）
├── product.ts         # 产品管理服务（CRUD、搜索、库存）
├── cart.ts            # 购物车服务（添加、更新、折扣）
├── order.ts           # 订单处理服务（创建、状态管理）
├── payment.ts         # 支付处理服务（支付、退款）
├── notification.ts    # 通知服务（发送、查询、标记已读）
└── index.ts           # 主应用入口（整合所有模块）
```

## 数据流特点

### 1. 多层导入导出
- `types.ts` 被所有模块导入
- `utils.ts` 提供通用工具函数
- 各业务模块互相调用

### 2. 复杂引用关系
- `auth.ts` ← `notification.ts` ← `order.ts`
- `product.ts` ← `cart.ts` ← `order.ts`
- `order.ts` ← `payment.ts` ← `notification.ts`
- `index.ts` 整合所有模块

### 3. 循环依赖场景
- `auth.ts` 调用 `order.getUserOrders()`
- `order.ts` 调用 `auth.getUserById()`
- `notification.ts` 调用 `auth.getUserById()`

### 4. 变量传递链
```
User (auth) → Cart (cart) → Order (order) → Payment (payment) → Notification (notification)
Product (product) → CartItem (cart) → OrderItem (order)
```

## 测试场景

1. **用户注册流程**: auth → notification
2. **购物流程**: product → cart → order → payment → notification
3. **库存管理**: product → notification (价格变化、库存预警)
4. **订单管理**: order → payment → notification (状态更新)

## 可视化预期

- **9 个文件节点**
- **50+ 个函数节点**
- **100+ 条数据流边**
- **多个循环依赖环**
- **复杂的类型传递链**
