import { json } from '@sveltejs/kit';
import { z } from 'zod';
import type { RequestHandler } from './$types';
import { markMockPaymentPaid } from '../../../../lib/server/billing';
import { isPaynowMock } from '../../../../lib/server/paynow';
import { rateLimit, rateLimitKey, tooManyRequests } from '../../../../lib/server/rate-limit';

const input = z.object({ reference: z.string().min(3).max(80) }).strict();

export const POST: RequestHandler = async (event) => {
	if (!isPaynowMock()) {
		return json({ error: 'Not found' }, { status: 404 });
	}
	if (!event.locals.user) {
		return json({ error: 'Unauthorized' }, { status: 401 });
	}

	const limit = await rateLimit(rateLimitKey(event, 'billing:mock-pay'), 10, 60);
	if (!limit.allowed) return tooManyRequests(limit);

	let body: unknown;
	try {
		body = await event.request.json();
	} catch {
		return json({ error: 'Invalid JSON body' }, { status: 400 });
	}

	const parsed = input.safeParse(body);
	if (!parsed.success) {
		return json({ error: 'Invalid reference' }, { status: 400 });
	}

	const payment = await markMockPaymentPaid(event.locals.user.id, parsed.data.reference);
	if (!payment) {
		return json({ error: 'Payment not found' }, { status: 404 });
	}

	return json({ ok: true, redirect: '/billing/success' });
};
