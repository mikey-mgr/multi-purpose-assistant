import type { KitAttachment } from './db/schema';
import { buildEml } from './mime';

export const MAX_ATTACHMENT_BYTES = 8 * 1024 * 1024;

export function decodedBase64Size(value: string): number {
	const clean = value.replace(/\s+/g, '');
	if (!clean) return 0;
	const padding = clean.endsWith('==') ? 2 : clean.endsWith('=') ? 1 : 0;
	return Math.floor((clean.length * 3) / 4) - padding;
}

export function safeFilename(value: string, fallback = 'mukana-application'): string {
	const cleaned = value
		.normalize('NFKD')
		.replace(/[^\w.\- ]+/g, '')
		.replace(/\s+/g, ' ')
		.replace(/-+/g, '-')
		.replace(/^[-.]+|[-.]+$/g, '')
		.slice(0, 100);
	return cleaned || fallback;
}

export function buildApplicationEml(kit: {
	recipient: string;
	subject: string;
	body: string;
	attachments: KitAttachment[];
}): string {
	return buildEml({
		to: kit.recipient,
		subject: kit.subject,
		body: kit.body,
		attachments: kit.attachments
	});
}
