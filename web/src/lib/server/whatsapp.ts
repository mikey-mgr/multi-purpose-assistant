import { timingSafeEqual } from './crypto';
import { envValue } from './env';

export type WhatsappMessage = {
	phone: string;
	body: string;
	fromMe: boolean;
	event: string;
	messageId: string | null;
	/** True when the payload came from a group, broadcast or newsletter. */
	isGroup: boolean;
	raw: unknown;
};

export function normalizePhone(value: string): string {
	return value
		.replace(/@s\.whatsapp\.net$/i, '')
		.replace(/@c\.us$/i, '')
		.replace(/[^\d]/g, '');
}

/** Normalise a Zimbabwean number to 2637... so 0778... and 263778... match. */
export function canonicalPhone(value: string): string {
	const digits = normalizePhone(value);
	return digits.startsWith('0') ? `263${digits.slice(1)}` : digits;
}

/**
 * Resolve the JID that actually identifies a person.
 *
 * WhatsApp now routes many chats through "@lid" (a linked device id) and only
 * exposes the phone number in `remoteJidAlt`. Groups/communities use "@g.us"
 * with a synthetic id, which is not a phone number at all - reading it as one
 * produced junk like "2637741196921423666047".
 */
export function resolveSenderJid(key: Record<string, unknown> | undefined): {
	jid: string | null;
	isGroup: boolean;
} {
	const remote = typeof key?.remoteJid === 'string' ? key.remoteJid : '';
	const alt = typeof key?.remoteJidAlt === 'string' ? key.remoteJidAlt : '';

	if (!remote && !alt) return { jid: null, isGroup: false };

	if (remote.endsWith('@g.us')) return { jid: null, isGroup: true };
	if (remote.endsWith('@broadcast') || remote.endsWith('@newsletter')) {
		return { jid: null, isGroup: true };
	}

	// Prefer a real phone JID; fall back to the lid only when nothing else exists.
	if (remote.endsWith('@s.whatsapp.net') || remote.endsWith('@c.us')) {
		return { jid: remote, isGroup: false };
	}
	if (alt.endsWith('@s.whatsapp.net') || alt.endsWith('@c.us')) {
		return { jid: alt, isGroup: false };
	}

	// A bare @lid with no phone alternative cannot be matched to an account.
	if (remote.endsWith('@lid')) return { jid: null, isGroup: false };

	return { jid: remote || alt || null, isGroup: false };
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

	// A group message is never a user talking to us; drop it before it reaches
	// the database or the job pipeline.
	const sender = resolveSenderJid(key);
	if (sender.isGroup) return null;
	if (!sender.jid) return null;

	const phone = canonicalPhone(sender.jid);
	if (!phone || phone.length < 10 || phone.length > 15) return null;

	const body = messageText(entry.message as Record<string, unknown> | undefined).trim();
	const messageId = typeof key?.id === 'string' ? key.id : null;

	return {
		phone,
		body,
		fromMe,
		event: event || 'messages.upsert',
		messageId,
		isGroup: false,
		raw: payload
	};
}

export async function sendWhatsappText(phone: string, body: string): Promise<boolean> {
	const base = envValue('WHATSAPP_API_URL');
	const key = envValue('WHATSAPP_API_KEY');
	const instance = envValue('WHATSAPP_INSTANCE_NAME') ?? 'Apex_Web_Services';
	if (!base || !key || !body.trim()) return false;

	const number = normalizePhone(phone);
	if (!number) return false;

	try {
		const response = await fetch(
			`${base.replace(/\/$/, '')}/message/sendText/${encodeURIComponent(instance)}`,
			{
				method: 'POST',
				headers: {
					'Content-Type': 'application/json',
					apikey: key
				},
				body: JSON.stringify({ number, text: body }),
				signal: AbortSignal.timeout(15000)
			}
		);
		return response.ok;
	} catch {
		return false;
	}
}

/**
 * Send one document over WhatsApp.
 *
 * Evolution takes media as base64 with a filename, so the caller passes raw
 * bytes rather than a URL we would have to expose publicly.
 */
export async function sendWhatsappDocument(input: {
	phone: string;
	base64: string;
	filename: string;
	mimetype: string;
	caption?: string;
}): Promise<boolean> {
	const base = envValue('WHATSAPP_API_URL');
	const key = envValue('WHATSAPP_API_KEY');
	const instance = envValue('WHATSAPP_INSTANCE_NAME') ?? 'Apex_Web_Services';
	if (!base || !key || !input.base64) return false;

	const number = normalizePhone(input.phone);
	if (!number) return false;

	try {
		const response = await fetch(
			`${base.replace(/\/$/, '')}/message/sendMedia/${encodeURIComponent(instance)}`,
			{
				method: 'POST',
				headers: {
					'Content-Type': 'application/json',
					apikey: key
				},
				body: JSON.stringify({
					number,
					mediatype: 'document',
					mimetype: input.mimetype,
					fileName: input.filename,
					caption: input.caption ?? '',
					media: input.base64
				}),
				signal: AbortSignal.timeout(60000)
			}
		);
		return response.ok;
	} catch {
		return false;
	}
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
