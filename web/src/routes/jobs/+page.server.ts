import { redirect } from '@sveltejs/kit';
import { and, desc, eq, ilike, isNotNull, or, sql } from 'drizzle-orm';
import { getDb } from '../../lib/server/db';
import { jobs } from '../../lib/server/db/schema';
import { publicSummary } from '../../lib/server/sanitize';

const PAGE_SIZE = 20;

export const load = async ({ locals, url }) => {
	if (!locals.user) redirect(303, '/login');

	const q = (url.searchParams.get('q') ?? '').trim().slice(0, 100);
	const category = (url.searchParams.get('category') ?? '').trim().slice(0, 100);
	const location = (url.searchParams.get('location') ?? '').trim().slice(0, 100);
	const page = Math.max(1, Number(url.searchParams.get('page') ?? 1) || 1);
	const offset = (page - 1) * PAGE_SIZE;

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
	const [rows, totalRows, categoryRows] = await Promise.all([
		db
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
			.limit(PAGE_SIZE)
			.offset(offset),
		db.select({ count: sql<number>`count(*)::int` }).from(jobs).where(where),
		db
			.selectDistinct({ category: jobs.category })
			.from(jobs)
			.where(isNotNull(jobs.category))
			.orderBy(jobs.category)
			.limit(60)
	]);

	const total = totalRows[0]?.count ?? 0;

	return {
		jobs: rows.map((row) => ({
			id: row.publicId,
			title: row.title ?? 'Untitled role',
			company: row.company ?? 'Employer',
			location: row.location ?? 'Zimbabwe',
			type: row.jobType,
			compensation: row.compensation,
			datePosted: row.datePosted,
			category: row.category,
			remote: row.remote,
			summary: publicSummary(row.description)
		})),
		total,
		page,
		pages: Math.max(1, Math.ceil(total / PAGE_SIZE)),
		q,
		category,
		location,
		categories: categoryRows.map((row) => row.category).filter(Boolean) as string[]
	};
};
