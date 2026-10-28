import { json } from '@sveltejs/kit';
import { eq } from 'drizzle-orm';
import type { RequestHandler } from './$types';
import { getDb } from '../../../../lib/server/db';
import { jobs } from '../../../../lib/server/db/schema';
import { rateLimit, rateLimitKey, tooManyRequests } from '../../../../lib/server/rate-limit';
import { publicSummary } from '../../../../lib/server/sanitize';

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export const GET: RequestHandler = async (event) => {
	if (!event.locals.user) {
		return json({ error: 'Unauthorized' }, { status: 401 });
	}
	if (!UUID_RE.test(event.params.id)) {
		return json({ error: 'Not found' }, { status: 404 });
	}

	const limit = await rateLimit(rateLimitKey(event, 'jobs:get'), 120, 60);
	if (!limit.allowed) return tooManyRequests(limit);

	const db = await getDb();
	const row = await db
		.select({
			publicId: jobs.publicId,
			title: jobs.title,
			company: jobs.company,
			location: jobs.location,
			jobType: jobs.jobType,
			compensation: jobs.compensation,
			datePosted: jobs.datePosted,
			expires: jobs.expires,
			category: jobs.category,
			remote: jobs.remote,
			description: jobs.description,
			applyInstructions: jobs.applyInstructions
		})
		.from(jobs)
		.where(eq(jobs.publicId, event.params.id))
		.limit(1);

	if (!row[0]) {
		return json({ error: 'Not found' }, { status: 404 });
	}

	return json(
		{
			id: row[0].publicId,
			title: row[0].title,
			company: row[0].company,
			location: row[0].location,
			type: row[0].jobType,
			compensation: row[0].compensation,
			datePosted: row[0].datePosted,
			expires: row[0].expires,
			category: row[0].category,
			remote: row[0].remote,
			summary: publicSummary(row[0].description),
			applyInstructions: row[0].applyInstructions
				? publicSummary(row[0].applyInstructions.trim(), 1200)
				: null
		},
		{ headers: { 'Cache-Control': 'private, max-age=60' } }
	);
};
