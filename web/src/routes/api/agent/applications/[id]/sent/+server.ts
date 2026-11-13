import { json } from '@sveltejs/kit';
import { and, eq, sql } from 'drizzle-orm';
import { z } from 'zod';
import type { RequestHandler } from './$types';
import {
	agentRateKey,
	authenticateAgent
} from '../../../../../../lib/server/agent-auth';
import { getDb } from '../../../../../../lib/server/db';
import {
	applicationKits,
	jobMatches,
	jobs,
	profiles
} from '../../../../../../lib/server/db/schema';
import { rateLimit, tooManyRequests } from '../../../../../../lib/server/rate-limit';

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

const input = z
	.object({
		legacy_user_id: z.string().uuid(),
		match_id: z.string().uuid(),
		sent: z.boolean(),
		message_id: z.string().max(500).optional(),
		error: z.string().max(2000).optional()
	})
	.strict();

export const POST: RequestHandler = async (event) => {
	const agent = await authenticateAgent(event, ['apply', 'both']);
	if (!agent) {
		return json({ error: 'Unauthorized' }, { status: 401 });
	}

	const id = event.params.id;
	if (!UUID_RE.test(id)) {
		return json({ error: 'Not found' }, { status: 404 });
	}

	const limit = await rateLimit(agentRateKey(agent.id, 'applications:sent'), 120, 60);
	if (!limit.allowed) return tooManyRequests(limit);

	let body: unknown;
	try {
		body = await event.request.json();
	} catch {
		return json({ error: 'Invalid JSON body' }, { status: 400 });
	}

	const parsed = input.safeParse(body);
	if (!parsed.success) {
		return json({ error: 'Invalid result', issues: parsed.error.flatten() }, { status: 400 });
	}

	// An agent may only report on the account it is bound to.
	if (!agent.userId || agent.userId !== parsed.data.legacy_user_id) {
		return json({ error: 'Forbidden' }, { status: 403 });
	}

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
	if (profileRows[0]?.legacyUserId !== parsed.data.legacy_user_id) {
		return json({ error: 'Forbidden' }, { status: 403 });
	}

	const matchRows = await db
		.select({ id: jobMatches.id, status: jobMatches.status })
		.from(jobMatches)
		.innerJoin(jobs, eq(jobMatches.jobId, jobs.id))
		.where(
			and(
				eq(jobMatches.id, parsed.data.match_id),
				eq(jobMatches.userId, kit.userId),
				sql`${jobs.publicId}::text = ${kit.jobId}`
			)
		)
		.limit(1);
	const match = matchRows[0];
	if (!match) {
		return json({ error: 'Match not found' }, { status: 404 });
	}

	if (parsed.data.sent) {
		if (match.status === 'applied') {
			return json({
				status: 'applied',
				matchId: match.id,
				alreadyApplied: true,
				messageId: parsed.data.message_id ?? null
			});
		}
		if (match.status !== 'generated') {
			return json(
				{ error: `Match is ${match.status}`, status: match.status },
				{ status: 409 }
			);
		}

		await db
			.update(jobMatches)
			.set({ status: 'applied' })
			.where(and(eq(jobMatches.id, match.id), eq(jobMatches.status, 'generated')));
	}

	return json({
		status: parsed.data.sent ? 'applied' : match.status,
		matchId: match.id,
		sent: parsed.data.sent,
		messageId: parsed.data.message_id ?? null,
		error: parsed.data.error ?? null
	});
};
