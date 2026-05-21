// Notification Service
export async function sendNotification(userId: string, message: string): Promise<void>
export async function sendEmail(to: string, subject: string, body: string): Promise<void> {}
export async function sendSMS(phone: string, message: string): Promise<void> {}
