import { timingSafeEqual } from './crypto';
import { envValue } from './env';

export type WhatsappMessage = {
	phone: string;
	body: string;
	fromMe: boolean;
	event: string;
	messageId: string | null;
	raw: unknown;
};

export function normalizePhone(value: string): string {
	return value
		.replace(/@s\.whatsapp\.net$/i, '')
		.replace(/@c\.us$/i, '')
		.replace(/[^\d]/g, '');
}

export function isWhatsappConfigured(): boolean {
	return Boolean(envValue('WHATSAPP_WEBHOOK_SECRET'));
}

export function verifyWhatsappSecret(header: string | null): boolean {
	const secret = envValue('WHATSAPP_WEBHOOK_SECRET');
	if (!secret || !header) return false;
	return timingSafeEqual(secret, header);
}

function messageText(message: Record<string, unknown> | undefined): string {
	if (!message) return '';
	const conversation = message.conversation;
	if (typeof conversation === 'string') return conversation;
	const extended = message.extendedTextMessage as { text?: string } | undefined;
	if (extended?.text) return extended.text;
	const image = message.imageMessage as { caption?: string } | undefined;
	if (image?.caption) return image.caption;
	const video = message.videoMessage as { caption?: string } | undefined;
	if (video?.caption) return video.caption;
	return '';
}

export function extractWhatsappMessage(payload: unknown): WhatsappMessage | null {
	if (!payload || typeof payload !== 'object') return null;
	const root = payload as Record<string, unknown>;
	const event = typeof root.event === 'string' ? root.event : '';
	if (event && event !== 'messages.upsert') return null;

	const rawData = root.data;
	const data = Array.isArray(rawData) ? rawData[0] : rawData;
	if (!data || typeof data !== 'object') return null;

	const entry = data as Record<string, unknown>;
	const key = entry.key as Record<string, unknown> | undefined;
	const remoteJid = typeof key?.remoteJid === 'string' ? key.remoteJid : '';
	const fromMe = Boolean(key?.fromMe);
	if (!remoteJid || fromMe) return null;

	const phone = normalizePhone(remoteJid);
	if (!phone) return null;

	const body = messageText(entry.message as Record<string, unknown> | undefined).trim();
	const messageId = typeof key?.id === 'string' ? key.id : null;

	return { phone, body, fromMe, event: event || 'messages.upsert', messageId, raw: payload };
}

export async function forwardWhatsappPayload(payload: unknown): Promise<void> {
	const url = envValue('WHATSAPP_FORWARD_URL');
	if (!url) return;
	const secret = envValue('WHATSAPP_WEBHOOK_SECRET') ?? '';
	await fetch(url, {
		method: 'POST',
		headers: {
			'Content-Type': 'application/json',
			'x-webhook-secret': secret
		},
		body: JSON.stringify(payload)
	});
}
