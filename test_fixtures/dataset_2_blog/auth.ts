// Auth for Blog
export interface User { id: string; email: string; name: string; }
export async function authenticateUser(token: string): Promise<User | null> { return null; }
export async function register(email: string, password: string): Promise<User> { return { id: '1', email, name: '' }; }
export async function login(email: string, password: string): Promise<string> { return 'token'; }
