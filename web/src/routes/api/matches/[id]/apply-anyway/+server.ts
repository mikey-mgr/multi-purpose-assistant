import { json } from '@sveltejs/kit';
import { and, eq } from 'drizzle-orm';
import type { RequestHandler } from './$types';
import { getDb } from '../../../../../lib/server/db';
import { jobMatches, jobs, profiles } from '../../../../../lib/server/db/schema';
import { envValue } from '../../../../../lib/server/env';
import { rateLimit, rateLimitKey, tooManyRequests } from '../../../../../lib/server/rate-limit';
import { rebuildApplication } from '../../../../../lib/server/resume/rebuild';

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/**
 * Force-send despite review blockers.
 *
 * Restricted to the owner's linked profile for now. When per-user apply agents
 * ship, this gate becomes "the user has a connected agent".
 */
export const POST: RequestHandler = async (event) => {
	if (!event.locals.user) {
		return json({ error: 'Unauthorized' }, { status: 401 });
	}
	if (!UUID_RE.test(event.params.id)) {
		return json({ error: 'Not found' }, { status: 404 });
	}

	const limit = await rateLimit(rateLimitKey(event, 'matches:apply-anyway'), 5, 300);
	if (!limit.allowed) return tooManyRequests(limit);

	const db = await getDb();
	const rows = await db
		.select({ legacyUserId: profiles.legacyUserId, status: jobMatches.status })
		.from(jobMatches)
		.innerJoin(profiles, eq(profiles.userId, jobMatches.userId))
		.innerJoin(jobs, eq(jobMatches.jobId, jobs.id))
		.where(
			and(
				eq(jobMatches.id, event.params.id),
				eq(jobMatches.userId, event.locals.user.id)
			)
		)
		.limit(1);

	const row = rows[0];
	if (!row) return json({ error: 'Match not found' }, { status: 404 });
	if (row.status === 'applied') {
		return json({ error: 'This application has already been sent' }, { status: 409 });
	}

	const ownerLegacyUserId = envValue('APPLY_AGENT_LEGACY_USER_ID');
	if (!ownerLegacyUserId || row.legacyUserId !== ownerLegacyUserId) {
		return json(
			{
				error:
					'Force-apply needs a connected apply agent. This account does not have one yet.',
				kind: 'no_agent'
			},
			{ status: 409 }
		);
	}

	const result = await rebuildApplication(event.params.id, event.locals.user.id, {
		force: true,
		queueSend: true
	});
	if (!result.ok) {
		return json({ error: result.error ?? 'Could not prepare the application' }, { status: 400 });
	}
	if (!result.queuedSend) {
		return json(
			{ error: 'The application was rebuilt but could not be queued for sending' },
			{ status: 409 }
		);
	}

	return json({
		ok: true,
		queued: true,
		kitId: result.kitId,
		blockers: result.blockers,
		message: 'Queued for sending. The apply agent will deliver it within a minute.'
	});
};
