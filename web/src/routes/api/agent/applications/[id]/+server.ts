import { json } from '@sveltejs/kit';
import { and, desc, eq, sql } from 'drizzle-orm';
import type { RequestHandler } from './$types';
import { agentRateKey, authenticateAgent } from '../../../../../lib/server/agent-auth';
import { getDb } from '../../../../../lib/server/db';
import { applicationKits, jobMatches, jobs, profiles } from '../../../../../lib/server/db/schema';
import { rateLimit, tooManyRequests } from '../../../../../lib/server/rate-limit';

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export const GET: RequestHandler = async (event) => {
	const agent = await authenticateAgent(event, ['apply', 'both']);
	if (!agent) {
		return json({ error: 'Unauthorized' }, { status: 401 });
	}

	const id = event.params.id;
	if (!UUID_RE.test(id)) {
		return json({ error: 'Not found' }, { status: 404 });
	}

	const legacyUserId = event.url.searchParams.get('legacy_user_id');
	if (!legacyUserId || !UUID_RE.test(legacyUserId)) {
		return json({ error: 'legacy_user_id is required' }, { status: 400 });
	}

	// An agent may only read kits belonging to the account it is bound to.
	if (!agent.userId || agent.userId !== legacyUserId) {
		return json({ error: 'Forbidden' }, { status: 403 });
	}

	const limit = await rateLimit(agentRateKey(agent.id, 'applications:kit'), 120, 60);
	if (!limit.allowed) return tooManyRequests(limit);

	const db = await getDb();
	const kitRows = await db
		.select()
		.from(applicationKits)
		.where(eq(applicationKits.id, id))
		.limit(1);
	const kit = kitRows[0];
	if (!kit) {
		return json({ error: 'Not found' }, { status: 404 });
	}

	const profileRows = await db
		.select({ legacyUserId: profiles.legacyUserId })
		.from(profiles)
		.where(eq(profiles.userId, kit.userId))
		.limit(1);
	if (profileRows[0]?.legacyUserId !== legacyUserId) {
		return json({ error: 'Forbidden' }, { status: 403 });
	}

	const matchRows = await db
		.select({ id: jobMatches.id, status: jobMatches.status })
		.from(jobMatches)
		.innerJoin(jobs, eq(jobMatches.jobId, jobs.id))
		.where(
			and(
				eq(jobMatches.userId, kit.userId),
				sql`${jobs.publicId}::text = ${kit.jobId}`
			)
		)
		.orderBy(desc(jobMatches.createdAt))
		.limit(1);
	const match = matchRows[0];
	if (!match) {
		return json({ error: 'Match not found' }, { status: 404 });
	}
	if (match.status !== 'generated') {
		return json(
			{ error: `Match is ${match.status}`, status: match.status },
			{ status: 409 }
		);
	}

	return json(
		{
			id: kit.id,
			matchId: match.id,
			status: match.status,
			jobTitle: kit.jobTitle,
			company: kit.company,
			recipient: kit.recipient,
			subject: kit.subject,
			body: kit.body,
			attachments: kit.attachments,
			metadata: kit.metadata,
			createdAt: kit.createdAt
		},
		{ headers: { 'Cache-Control': 'no-store' } }
	);
};
