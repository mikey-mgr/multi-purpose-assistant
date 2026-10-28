import { json } from '@sveltejs/kit';
import { and, desc, eq, ilike, or, sql } from 'drizzle-orm';
import type { RequestHandler } from './$types';
import { getDb } from '../../../lib/server/db';
import { jobs } from '../../../lib/server/db/schema';
import { rateLimit, rateLimitKey, tooManyRequests } from '../../../lib/server/rate-limit';
import { publicSummary } from '../../../lib/server/sanitize';

function clamp(value: number, min: number, max: number) {
	return Math.min(max, Math.max(min, value));
}

export const GET: RequestHandler = async (event) => {
	if (!event.locals.user) {
		return json({ error: 'Unauthorized' }, { status: 401 });
	}

	const limit = await rateLimit(rateLimitKey(event, 'jobs:list'), 60, 60);
	if (!limit.allowed) return tooManyRequests(limit);

	const params = event.url.searchParams;
	const take = clamp(Number(params.get('limit') ?? 20) || 20, 1, 50);
	const offset = Math.max(0, Number(params.get('offset') ?? 0) || 0);
	const q = (params.get('q') ?? '').trim().slice(0, 100);
	const category = (params.get('category') ?? '').trim().slice(0, 100);
	const location = (params.get('location') ?? '').trim().slice(0, 100);

	const filters = [];
	if (q) {
		filters.push(
			or(
				ilike(jobs.title, `%${q}%`),
				ilike(jobs.company, `%${q}%`),
				ilike(jobs.description, `%${q}%`)
			)
		);
	}
	if (category) filters.push(eq(jobs.category, category));
	if (location) filters.push(ilike(jobs.location, `%${location}%`));
	const where = filters.length ? and(...filters) : undefined;

	const db = await getDb();
	const rows = await db
		.select({
			publicId: jobs.publicId,
			title: jobs.title,
			company: jobs.company,
			location: jobs.location,
			jobType: jobs.jobType,
			compensation: jobs.compensation,
			datePosted: jobs.datePosted,
			category: jobs.category,
			remote: jobs.remote,
			description: jobs.description
		})
		.from(jobs)
		.where(where)
		.orderBy(desc(jobs.datePosted), desc(jobs.scrapedAt))
		.limit(take)
		.offset(offset);

	const totalRows = await db
		.select({ count: sql<number>`count(*)::int` })
		.from(jobs)
		.where(where);

	return json(
		{
			jobs: rows.map((row) => ({
				id: row.publicId,
				title: row.title,
				company: row.company,
				location: row.location,
				type: row.jobType,
				compensation: row.compensation,
				datePosted: row.datePosted,
				category: row.category,
				remote: row.remote,
				summary: publicSummary(row.description)
			})),
			total: totalRows[0]?.count ?? 0,
			limit: take,
			offset
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
