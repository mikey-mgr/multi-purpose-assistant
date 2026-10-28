import { json, redirect } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { randomToken } from '../../../../../lib/server/crypto';
import { getDb } from '../../../../../lib/server/db';
import { oauthStates } from '../../../../../lib/server/db/schema';
import { buildGmailAuthUrl } from '../../../../../lib/server/gmail';
import { rateLimit, rateLimitKey, tooManyRequests } from '../../../../../lib/server/rate-limit';

export const GET: RequestHandler = async (event) => {
	if (!event.locals.user) {
		return json({ error: 'Unauthorized' }, { status: 401 });
	}

	const limit = await rateLimit(rateLimitKey(event, 'gmail:connect'), 10, 3600);
	if (!limit.allowed) return tooManyRequests(limit);

	const state = randomToken(32);
	const db = await getDb();
	await db.insert(oauthStates).values({
		id: state,
		userId: event.locals.user.id,
		provider: 'gmail',
		expiresAt: new Date(Date.now() + 10 * 60 * 1000)
	});

	redirect(302, buildGmailAuthUrl(state));
};
