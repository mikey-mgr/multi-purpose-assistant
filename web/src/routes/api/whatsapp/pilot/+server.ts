import { json } from '@sveltejs/kit';
import { eq, sql } from 'drizzle-orm';
import { z } from 'zod';
import type { RequestHandler } from './$types';
import { getDb } from '../../../../lib/server/db';
import { whatsappPilot } from '../../../../lib/server/db/schema';
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

	const countRows = await db
		.select({ count: sql<number>`count(*)::int` })
		.from(whatsappPilot)
		.where(eq(whatsappPilot.status, 'active'));
	const active = countRows[0]?.count ?? 0;

	const slot = active < PILOT_SLOTS ? active + 1 : null;
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
