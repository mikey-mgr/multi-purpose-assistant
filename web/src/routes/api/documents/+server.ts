import { json } from '@sveltejs/kit';
import { desc, eq } from 'drizzle-orm';
import type { RequestHandler } from './$types';
import { getDb } from '../../../lib/server/db';
import { documents, jobs } from '../../../lib/server/db/schema';
import { rateLimit, rateLimitKey, tooManyRequests } from '../../../lib/server/rate-limit';

function clamp(value: number, min: number, max: number) {
	return Math.min(max, Math.max(min, value));
}

export const GET: RequestHandler = async (event) => {
	if (!event.locals.user) {
		return json({ error: 'Unauthorized' }, { status: 401 });
	}

	const limit = await rateLimit(rateLimitKey(event, 'documents:list'), 120, 60);
	if (!limit.allowed) return tooManyRequests(limit);

	const take = clamp(Number(event.url.searchParams.get('limit') ?? 50) || 50, 1, 100);
	const type = event.url.searchParams.get('type');

	const db = await getDb();
	const rows = await db
		.select({
			id: documents.id,
			documentType: documents.documentType,
			promptName: documents.promptName,
			model: documents.model,
			tokensUsed: documents.tokensUsed,
			createdAt: documents.createdAt,
			jobId: jobs.publicId,
			jobTitle: jobs.title,
			company: jobs.company
		})
		.from(documents)
		.leftJoin(jobs, eq(documents.jobId, jobs.id))
		.where(eq(documents.userId, event.locals.user.id))
		.orderBy(desc(documents.createdAt))
		.limit(take);

	return json(
		{
			documents: rows
				.filter((row) => (type ? row.documentType === type : true))
				.map((row) => ({
					id: row.id,
					type: row.documentType,
					promptName: row.promptName,
					model: row.model,
					tokensUsed: row.tokensUsed,
					createdAt: row.createdAt,
					jobId: row.jobId,
					jobTitle: row.jobTitle,
					company: row.company
				}))
		},
		{
			headers: {
				'Cache-Control': 'private, max-age=60',
				'X-RateLimit-Limit': String(limit.limit),
				'X-RateLimit-Remaining': String(limit.remaining)
			}
		}
	);
};
