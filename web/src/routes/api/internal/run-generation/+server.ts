import { json } from '@sveltejs/kit';
import { and, eq, isNotNull, notLike, or, sql } from 'drizzle-orm';
import type { RequestHandler } from './$types';
import { getDb } from '../../../../lib/server/db';
import { profiles, user } from '../../../../lib/server/db/schema';
import { timingSafeEqual } from '../../../../lib/server/crypto';
import { envValue } from '../../../../lib/server/env';
import { generateForMatchedJob } from '../../../../lib/server/generation';

export const POST: RequestHandler = async (event) => {
	const expected = envValue('SCHEDULER_SECRET');
	const supplied = event.request.headers.get('x-scheduler-secret');
	if (!expected || !supplied || !timingSafeEqual(expected, supplied)) {
		return json({ error: 'Unauthorized' }, { status: 401 });
	}

	let body: { dry_run?: unknown; auto_send?: unknown } = {};
	try {
		body = (await event.request.json()) as { dry_run?: unknown; auto_send?: unknown };
	} catch {
		body = {};
	}
	const dryRun = body.dry_run === true;
	const allowSend = body.auto_send === true;

	const db = await getDb();
	const users = await db
		.select({ userId: profiles.userId })
		.from(profiles)
		.innerJoin(user, eq(profiles.userId, user.id))
		.where(
			and(
				eq(profiles.onboardingCompleted, true),
				notLike(user.email, '%@example.com'),
				or(isNotNull(profiles.resumeData), isNotNull(profiles.resumeText)),
				sql`exists (
					select 1 from job_matches m
					join jobs j on j.id = m.job_id
					where m.user_id = ${profiles.userId}
					  and m.status = 'matched'
					  and (j.expires is null or j.expires >= current_date)
				)`
			)
		)
		.limit(1);

	const results = [];
	for (const row of users) {
		results.push({ userId: row.userId, ...(await generateForMatchedJob(row.userId, { dryRun, allowSend })) });
	}

	return json({
		checked: users.length,
		dryRun,
		allowSend,
		generated: results.filter((result) => result.generated).length,
		results
	});
};
