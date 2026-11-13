import { json } from '@sveltejs/kit';
import { and, eq, gte } from 'drizzle-orm';
import type { RequestHandler } from './$types';
import { getDb } from '../../../../lib/server/db';
import { jobMatches, profiles } from '../../../../lib/server/db/schema';
import { envValue } from '../../../../lib/server/env';
import { rateLimit, rateLimitKey, tooManyRequests } from '../../../../lib/server/rate-limit';

export const POST: RequestHandler = async (event) => {
	if (!event.locals.user) {
		return json({ error: 'Unauthorized' }, { status: 401 });
	}

	const limit = await rateLimit(rateLimitKey(event, 'matches:reevaluate'), 2, 3600);
	if (!limit.allowed) return tooManyRequests(limit);

	const target = envValue('MATCH_TRIGGER_URL');
	const secret = envValue('MATCH_TRIGGER_SECRET');
	if (!target || !secret) {
		return json({ error: 'Matching service is not configured' }, { status: 503 });
	}

	const db = await getDb();
	const cutoff = new Date(Date.now() - 30 * 24 * 60 * 60 * 1000);
	await db
		.delete(jobMatches)
		.where(
			and(
				eq(jobMatches.userId, event.locals.user.id),
				eq(jobMatches.status, 'rejected'),
				gte(jobMatches.createdAt, cutoff)
			)
		);

	const profile = await db
		.select({ legacyUserId: profiles.legacyUserId, matchSince: profiles.matchSince })
		.from(profiles)
		.where(eq(profiles.userId, event.locals.user.id))
		.limit(1);

	const response = await fetch(target, {
		method: 'POST',
		headers: {
			'Content-Type': 'application/json',
			'x-match-trigger-secret': secret
		},
		body: JSON.stringify({
			user_id: profile[0]?.legacyUserId ?? event.locals.user.id,
			web_user_id: event.locals.user.id,
			legacy_user_id: profile[0]?.legacyUserId ?? null,
			match_since: profile[0]?.matchSince?.toISOString() ?? null,
			limit: 50
		})
	});

	if (!response.ok) {
		return json({ error: 'Could not restart matching' }, { status: 502 });
	}

	return json(
		{ status: 'accepted' },
		{ headers: { 'Cache-Control': 'no-store' } }
	);
};
