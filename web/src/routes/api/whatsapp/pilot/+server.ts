import { json } from '@sveltejs/kit';
import { eq } from 'drizzle-orm';
import { z } from 'zod';
import type { RequestHandler } from './$types';
import { getDb } from '../../../../lib/server/db';
import { profiles, whatsappPilot } from '../../../../lib/server/db/schema';
import { normalizePhone } from '../../../../lib/server/whatsapp';
import { rateLimit, rateLimitKey, tooManyRequests } from '../../../../lib/server/rate-limit';

const PILOT_SLOTS = 15;

const input = z
	.object({
		phone: z.string().min(8).max(30)
	})
	.strict();

export const POST: RequestHandler = async (event) => {
	if (!event.locals.user) {
		return json({ error: 'Unauthorized' }, { status: 401 });
	}

	const limit = await rateLimit(rateLimitKey(event, 'whatsapp:pilot'), 5, 3600);
	if (!limit.allowed) return tooManyRequests(limit);

	let body: unknown;
	try {
		body = await event.request.json();
	} catch {
		return json({ error: 'Invalid JSON body' }, { status: 400 });
	}

	const parsed = input.safeParse(body);
	if (!parsed.success) {
		return json({ error: 'Invalid phone number' }, { status: 400 });
	}

	const phone = normalizePhone(parsed.data.phone);
	if (phone.length < 8 || phone.length > 15) {
		return json({ error: 'Invalid phone number' }, { status: 400 });
	}

	const db = await getDb();
	const existing = await db
		.select()
		.from(whatsappPilot)
		.where(eq(whatsappPilot.userId, event.locals.user.id))
		.limit(1);

	if (existing[0]) {
		return json({
			phone: existing[0].phone,
			slot: existing[0].slot,
			status: existing[0].status
		});
	}

	const usedRows = await db
		.select({ slot: whatsappPilot.slot })
		.from(whatsappPilot)
		.where(eq(whatsappPilot.status, 'active'));
	const used = new Set(usedRows.map((row) => row.slot).filter((slot) => slot !== null));
	let slot: number | null = null;
	for (let candidate = 1; candidate <= PILOT_SLOTS; candidate += 1) {
		if (!used.has(candidate)) {
			slot = candidate;
			break;
		}
	}
	const status = slot ? 'active' : 'waitlist';

	try {
		await db.insert(whatsappPilot).values({
			userId: event.locals.user.id,
			phone,
			slot,
			status
		});
	} catch {
		return json(
			{ error: 'Could not reserve a pilot slot. Try again.' },
			{ status: 409 }
		);
	}

	return json({ phone, slot, status });
};

export const DELETE: RequestHandler = async (event) => {
	if (!event.locals.user) {
		return json({ error: 'Unauthorized' }, { status: 401 });
	}
	const limit = await rateLimit(rateLimitKey(event, 'whatsapp:pilot:optout'), 5, 3600);
	if (!limit.allowed) return tooManyRequests(limit);

	const db = await getDb();
	await db.delete(whatsappPilot).where(eq(whatsappPilot.userId, event.locals.user.id));
	await db
		.update(profiles)
		.set({ whatsappPromptDismissedAt: new Date() })
		.where(eq(profiles.userId, event.locals.user.id));
	return json({ ok: true, optedOut: true });
};
