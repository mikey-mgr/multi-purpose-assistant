import { json } from '@sveltejs/kit';
import { and, eq } from 'drizzle-orm';
import type { RequestHandler } from './$types';
import { getDb } from '../../../../lib/server/db';
import { jobMatches, jobs } from '../../../../lib/server/db/schema';
import { rateLimit, rateLimitKey, tooManyRequests } from '../../../../lib/server/rate-limit';

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export const GET: RequestHandler = async (event) => {
	if (!event.locals.user) {
		return json({ error: 'Unauthorized' }, { status: 401 });
	}
	if (!UUID_RE.test(event.params.id)) {
		return json({ error: 'Not found' }, { status: 404 });
	}

	const limit = await rateLimit(rateLimitKey(event, 'matches:get'), 120, 60);
	if (!limit.allowed) return tooManyRequests(limit);

	const db = await getDb();
	const row = await db
		.select({
			matchId: jobMatches.id,
			status: jobMatches.status,
			score: jobMatches.score,
			reason: jobMatches.reason,
			proceed: jobMatches.proceed,
			applyAction: jobMatches.applyAction,
			applyRecipient: jobMatches.applyRecipient,
			applySubject: jobMatches.applySubject,
			applyBody: jobMatches.applyBody,
			applyUrl: jobMatches.applyUrl,
			requiredDocs: jobMatches.requiredDocs,
			expiryDate: jobMatches.expiryDate,
			createdAt: jobMatches.createdAt,
			jobId: jobs.publicId,
			title: jobs.title,
			company: jobs.company,
			location: jobs.location,
			jobType: jobs.jobType,
			compensation: jobs.compensation,
			datePosted: jobs.datePosted,
			remote: jobs.remote
		})
		.from(jobMatches)
		.innerJoin(jobs, eq(jobMatches.jobId, jobs.id))
		.where(
			and(eq(jobMatches.id, event.params.id), eq(jobMatches.userId, event.locals.user.id))
		)
		.limit(1);

	if (!row[0]) {
		return json({ error: 'Not found' }, { status: 404 });
	}

	return json(
		{
			id: row[0].matchId,
			status: row[0].status,
			score: row[0].score,
			summary: row[0].reason,
			proceed: row[0].proceed,
			applyAction: row[0].applyAction,
			applyRecipient: row[0].applyRecipient,
			applySubject: row[0].applySubject,
			applyBody: row[0].applyBody,
			applyUrl: row[0].applyUrl,
			requiredDocs: row[0].requiredDocs,
			expiryDate: row[0].expiryDate,
			createdAt: row[0].createdAt,
			job: {
				id: row[0].jobId,
				title: row[0].title,
				company: row[0].company,
				location: row[0].location,
				type: row[0].jobType,
				compensation: row[0].compensation,
				datePosted: row[0].datePosted,
				remote: row[0].remote
			}
		},
		{ headers: { 'Cache-Control': 'private, max-age=30' } }
	);
};
