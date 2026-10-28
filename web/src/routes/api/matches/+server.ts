import { json } from '@sveltejs/kit';
import { and, desc, eq, inArray } from 'drizzle-orm';
import type { RequestHandler } from './$types';
import { getDb } from '../../../lib/server/db';
import { jobMatches, jobs } from '../../../lib/server/db/schema';
import { rateLimit, rateLimitKey, tooManyRequests } from '../../../lib/server/rate-limit';
import { publicSummary } from '../../../lib/server/sanitize';

const ACTIVE_STATUSES = ['matched', 'generated', 'applied', 'waiting'];
const STATUSES = [...ACTIVE_STATUSES, 'rejected', 'duplicate', 'suspended'];

function clamp(value: number, min: number, max: number) {
	return Math.min(max, Math.max(min, value));
}

export const GET: RequestHandler = async (event) => {
	if (!event.locals.user) {
		return json({ error: 'Unauthorized' }, { status: 401 });
	}

	const limit = await rateLimit(rateLimitKey(event, 'matches:list'), 120, 60);
	if (!limit.allowed) return tooManyRequests(limit);

	const params = event.url.searchParams;
	const take = clamp(Number(params.get('limit') ?? 50) || 50, 1, 100);
	const status = params.get('status');
	const userFilter = eq(jobMatches.userId, event.locals.user.id);
	const where =
		status === 'all'
			? userFilter
			: status && STATUSES.includes(status)
				? and(userFilter, eq(jobMatches.status, status))
				: and(userFilter, inArray(jobMatches.status, ACTIVE_STATUSES));

	const db = await getDb();
	const rows = await db
		.select({
			matchId: jobMatches.id,
			status: jobMatches.status,
			score: jobMatches.score,
			reason: jobMatches.reason,
			proceed: jobMatches.proceed,
			applyAction: jobMatches.applyAction,
			applyRecipient: jobMatches.applyRecipient,
			applySubject: jobMatches.applySubject,
			createdAt: jobMatches.createdAt,
			jobId: jobs.publicId,
			title: jobs.title,
			company: jobs.company,
			location: jobs.location,
			jobType: jobs.jobType,
			compensation: jobs.compensation,
			datePosted: jobs.datePosted
		})
		.from(jobMatches)
		.innerJoin(jobs, eq(jobMatches.jobId, jobs.id))
		.where(where)
		.orderBy(desc(jobMatches.score), desc(jobMatches.createdAt))
		.limit(take);

	return json(
		{
			matches: rows.map((row) => ({
				id: row.matchId,
				jobId: row.jobId,
				status: row.status,
				score: row.score,
				summary: publicSummary(row.reason),
				proceed: row.proceed,
				applyAction: row.applyAction,
				applyRecipient: row.applyRecipient,
				applySubject: row.applySubject,
				createdAt: row.createdAt,
				job: {
					title: row.title,
					company: row.company,
					location: row.location,
					type: row.jobType,
					compensation: row.compensation,
					datePosted: row.datePosted
				}
			}))
		},
		{
			headers: {
				'Cache-Control': 'private, max-age=30',
				'X-RateLimit-Limit': String(limit.limit),
				'X-RateLimit-Remaining': String(limit.remaining)
			}
		}
	);
};
