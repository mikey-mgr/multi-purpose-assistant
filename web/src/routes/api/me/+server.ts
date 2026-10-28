import { json } from '@sveltejs/kit';
import { eq } from 'drizzle-orm';
import type { RequestHandler } from './$types';
import { getDb } from '../../../lib/server/db';
import { profiles } from '../../../lib/server/db/schema';
import { rateLimit, rateLimitKey, tooManyRequests } from '../../../lib/server/rate-limit';

export const GET: RequestHandler = async (event) => {
	if (!event.locals.user) {
		return json({ error: 'Unauthorized' }, { status: 401 });
	}

	const limit = await rateLimit(rateLimitKey(event, 'me'), 120, 60);
	if (!limit.allowed) return tooManyRequests(limit);

	const db = await getDb();
	const profile = await db
		.select()
		.from(profiles)
		.where(eq(profiles.userId, event.locals.user.id))
		.limit(1);

	return json(
		{
			user: event.locals.user,
			session: {
				expiresAt: event.locals.session?.expiresAt ?? null
			},
			profile: profile[0] ?? null
		},
		{
			headers: {
				'Cache-Control': 'no-store',
				'X-RateLimit-Limit': String(limit.limit),
				'X-RateLimit-Remaining': String(limit.remaining)
			}
		}
	);
};
