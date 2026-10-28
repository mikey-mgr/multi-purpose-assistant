import { json } from '@sveltejs/kit';
import { eq } from 'drizzle-orm';
import type { RequestHandler } from './$types';
import { getDb } from '../../../../lib/server/db';
import { whatsappMessages, whatsappPilot } from '../../../../lib/server/db/schema';
import {
	extractWhatsappMessage,
	forwardWhatsappPayload,
	verifyWhatsappSecret
} from '../../../../lib/server/whatsapp';
import { rateLimit, tooManyRequests } from '../../../../lib/server/rate-limit';

export const GET: RequestHandler = async () => {
	return json({ ok: true, service: 'mukana-whatsapp' });
};

export const POST: RequestHandler = async (event) => {
	const secret = event.request.headers.get('x-webhook-secret');
	if (!verifyWhatsappSecret(secret)) {
		return json({ error: 'Unauthorized' }, { status: 401 });
	}

	let payload: unknown;
	try {
		payload = await event.request.json();
	} catch {
		return json({ error: 'Invalid JSON body' }, { status: 400 });
	}

	const message = extractWhatsappMessage(payload);
	if (!message) {
		return json({ ok: true, ignored: true });
	}

	const limit = await rateLimit(`wa:${message.phone}`, 30, 60);
	if (!limit.allowed) return tooManyRequests(limit);

	const db = await getDb();
	const pilot = await db
		.select()
		.from(whatsappPilot)
		.where(eq(whatsappPilot.phone, message.phone))
		.limit(1);

	await db.insert(whatsappMessages).values({
		userId: pilot[0]?.status === 'active' ? pilot[0].userId : null,
		phone: message.phone,
		direction: 'inbound',
		body: message.body,
		raw: payload
	});

	const forward = forwardWhatsappPayload(payload).catch(() => undefined);
	if (event.platform?.ctx?.waitUntil) {
		event.platform.ctx.waitUntil(forward);
	} else {
		await forward;
	}

	return json({
		ok: true,
		matched: Boolean(pilot[0]),
		pilotStatus: pilot[0]?.status ?? null,
		slot: pilot[0]?.slot ?? null
	});
};
