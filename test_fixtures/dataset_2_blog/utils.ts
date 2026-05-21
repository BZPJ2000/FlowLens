// Utils for Blog
export function formatDate(date: Date): string { return date.toISOString(); }
export function sanitizeHtml(html: string): string { return html.replace(/<script>/g, ''); }
export function slugify(text: string): string { return text.toLowerCase().replace(/\s+/g, '-'); }
