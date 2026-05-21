// Product Service
export interface Product { id: string; name: string; price: number; stock: number; category: string; }
export async function getProducts(): Promise<Product[]> { return []; }
export async function updateStock(productId: string, delta: number): Promise<void> {}
export async function getProductById(id: string): Promise<Product | null> { return null; }
