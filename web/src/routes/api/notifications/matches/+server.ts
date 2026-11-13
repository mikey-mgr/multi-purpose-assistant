import { json } from '@sveltejs/kit';
import { z } from 'zod';
import type { RequestHandler } from './$types';
import { timingSafeEqual } from '../../../../lib/server/crypto';
import { envValue } from '../../../../lib/server/env';
import { notifyNewMatches } from '../../../../lib/server/notifications';

const input = z.object({ user_id: z.string().min(1).max(100) }).strict();

export const POST: RequestHandler = async (event) => {
	const expected = envValue('MATCH_TRIGGER_SECRET');
	const supplied = event.request.headers.get('x-match-trigger-secret');
	if (!expected || !supplied || !timingSafeEqual(expected, supplied)) {
		return json({ error: 'Unauthorized' }, { status: 401 });
	}

	let body: unknown;
	try {
		body = await event.request.json();
	} catch {
		return json({ error: 'Invalid JSON body' }, { status: 400 });
	}
	const parsed = input.safeParse(body);
	if (!parsed.success) {
		return json({ error: 'Invalid notification request' }, { status: 400 });
	}

	await notifyNewMatches(parsed.data.user_id, new Date(Date.now() - 5 * 60 * 1000));
	return json({ ok: true });
};
