import { json } from '@sveltejs/kit';
import { and, eq, isNotNull, notLike } from 'drizzle-orm';
import type { RequestHandler } from './$types';
import { getDb } from '../../../../lib/server/db';
import { profiles, user } from '../../../../lib/server/db/schema';
import { timingSafeEqual } from '../../../../lib/server/crypto';
import { envValue } from '../../../../lib/server/env';

export const POST: RequestHandler = async (event) => {
	const expected = envValue('SCHEDULER_SECRET');
	const supplied = event.request.headers.get('x-scheduler-secret');
	if (!expected || !supplied || !timingSafeEqual(expected, supplied)) {
		return json({ error: 'Unauthorized' }, { status: 401 });
	}

	const target = envValue('MATCH_TRIGGER_URL');
	const matchSecret = envValue('MATCH_TRIGGER_SECRET');
	if (!target || !matchSecret) {
		return json({ error: 'Matching service is not configured' }, { status: 503 });
	}

	const db = await getDb();
	const rows = await db
		.select({
			userId: profiles.userId,
			legacyUserId: profiles.legacyUserId,
			matchSince: profiles.matchSince
		})
		.from(profiles)
		.innerJoin(user, eq(profiles.userId, user.id))
		.where(
			and(
				eq(profiles.onboardingCompleted, true),
				notLike(user.email, '%@example.com'),
				isNotNull(profiles.headline)
			)
		)
		.limit(25);

	const runs = await Promise.allSettled(
		rows.map((row) =>
			fetch(target, {
				method: 'POST',
				headers: {
					'Content-Type': 'application/json',
					'x-match-trigger-secret': matchSecret
				},
				body: JSON.stringify({
					user_id: row.legacyUserId ?? row.userId,
					web_user_id: row.userId,
					legacy_user_id: row.legacyUserId ?? null,
					match_since: row.matchSince?.toISOString() ?? null,
					limit: 50
				})
			})
		)
	);

	return json({
		queued: runs.length,
		failed: runs.filter((run) => run.status === 'rejected').length
	});
};
