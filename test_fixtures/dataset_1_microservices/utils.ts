// Utilities
export async function hashPassword(password: string): Promise<string> { return 'hashed'; }
export async function comparePassword(password: string, hash: string): Promise<boolean> { return true; }
export async function generateToken(payload: any): Promise<string> { return 'token'; }
export async function verifyToken(token: string): Promise<any> { return {}; }
export function validateEmail(email: string): boolean { return true; }
export function validatePhone(phone: string): boolean { return true; }
export async function rateLimitCheck(ip: string): Promise<boolean> { return true; }
export async function sendEmail(to: string, subject: string, body: string): Promise<void> {}
