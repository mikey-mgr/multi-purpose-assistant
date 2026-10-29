import { json } from '@sveltejs/kit';
import { eq } from 'drizzle-orm';
import type { RequestHandler } from './$types';
import { getDb } from '../../../../lib/server/db';
import { profiles } from '../../../../lib/server/db/schema';
import { envValue } from '../../../../lib/server/env';
import { rateLimit, rateLimitKey, tooManyRequests } from '../../../../lib/server/rate-limit';

function triggerUrl(): string | null {
	const raw = envValue('MATCH_TRIGGER_URL');
	if (!raw) return null;
	try {
		const url = new URL(raw);
		const local =
			url.hostname === 'localhost' ||
			url.hostname === '127.0.0.1' ||
			url.hostname === '::1';
		if (url.protocol !== 'https:' && !(url.protocol === 'http:' && local)) return null;
		return url.toString();
	} catch {
		return null;
	}
}

export const POST: RequestHandler = async (event) => {
	if (!event.locals.user) {
		return json({ error: 'Unauthorized' }, { status: 401 });
	}

	const limit = await rateLimit(rateLimitKey(event, 'matches:run'), 5, 3600);
	if (!limit.allowed) return tooManyRequests(limit);

	const target = triggerUrl();
	const secret = envValue('MATCH_TRIGGER_SECRET');
	if (!target || !secret) {
		return json({ error: 'Matching service is not configured' }, { status: 503 });
	}

	const db = await getDb();
	const profile = await db
		.select({ legacyUserId: profiles.legacyUserId, matchSince: profiles.matchSince })
		.from(profiles)
		.where(eq(profiles.userId, event.locals.user.id))
		.limit(1);

	if (!profile[0]?.legacyUserId) {
		return json(
			{ error: 'This account is not linked to the matching pipeline' },
			{ status: 409 }
		);
	}

	try {
		const response = await fetch(target, {
			method: 'POST',
			headers: {
				'Content-Type': 'application/json',
				'x-match-trigger-secret': secret
			},
			body: JSON.stringify({
				user_id: profile[0].legacyUserId,
				match_since: profile[0].matchSince?.toISOString() ?? null,
				limit: 50
			}),
			signal: AbortSignal.timeout(15000)
		});

		if (!response.ok) {
			return json({ error: 'Matching service rejected the request' }, { status: 502 });
		}
	} catch {
		return json({ error: 'Matching service unreachable' }, { status: 502 });
	}

	return json(
		{ status: 'accepted' },
		{ headers: { 'Cache-Control': 'no-store' } }
	);
};
