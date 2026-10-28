import { json } from '@sveltejs/kit';
import { and, eq } from 'drizzle-orm';
import type { RequestHandler } from './$types';
import { getDb } from '../../../../lib/server/db';
import { documents, jobs } from '../../../../lib/server/db/schema';
import { rateLimit, rateLimitKey, tooManyRequests } from '../../../../lib/server/rate-limit';

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export const GET: RequestHandler = async (event) => {
	if (!event.locals.user) {
		return json({ error: 'Unauthorized' }, { status: 401 });
	}
	if (!UUID_RE.test(event.params.id)) {
		return json({ error: 'Not found' }, { status: 404 });
	}

	const limit = await rateLimit(rateLimitKey(event, 'documents:get'), 120, 60);
	if (!limit.allowed) return tooManyRequests(limit);

	const db = await getDb();
	const row = await db
		.select({
			id: documents.id,
			documentType: documents.documentType,
			content: documents.content,
			rendercvYaml: documents.rendercvYaml,
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
		.where(and(eq(documents.id, event.params.id), eq(documents.userId, event.locals.user.id)))
		.limit(1);

	if (!row[0]) {
		return json({ error: 'Not found' }, { status: 404 });
	}

	return json(
		{
			id: row[0].id,
			type: row[0].documentType,
			content: row[0].content,
			rendercvYaml: row[0].rendercvYaml,
			promptName: row[0].promptName,
			model: row[0].model,
			tokensUsed: row[0].tokensUsed,
			createdAt: row[0].createdAt,
			job: {
				id: row[0].jobId,
				title: row[0].jobTitle,
				company: row[0].company
			}
		},
		{ headers: { 'Cache-Control': 'private, max-age=60' } }
	);
};
