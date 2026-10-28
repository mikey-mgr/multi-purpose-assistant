import { redirect } from '@sveltejs/kit';
import { and, desc, eq, inArray, sql } from 'drizzle-orm';
import { getDb } from '../../lib/server/db';
import { jobMatches, jobs } from '../../lib/server/db/schema';
import { publicSummary } from '../../lib/server/sanitize';

const PAGE_SIZE = 25;
const ACTIVE_STATUSES = ['matched', 'generated', 'applied', 'waiting'];
const STATUSES = [...ACTIVE_STATUSES, 'rejected', 'duplicate', 'suspended'];

export const load = async ({ locals, url }) => {
	if (!locals.user) redirect(303, '/login');

	const requested = url.searchParams.get('status') ?? 'active';
	const status = requested === 'all' || STATUSES.includes(requested) ? requested : 'active';
	const page = Math.max(1, Number(url.searchParams.get('page') ?? 1) || 1);
	const userId = locals.user.id;

	const userFilter = eq(jobMatches.userId, userId);
	const where =
		status === 'all'
			? userFilter
			: status === 'active'
				? and(userFilter, inArray(jobMatches.status, ACTIVE_STATUSES))
				: and(userFilter, eq(jobMatches.status, status));

	const db = await getDb();
	const [rows, totalRows, statusRows] = await Promise.all([
		db
			.select({
				matchId: jobMatches.id,
				status: jobMatches.status,
				score: jobMatches.score,
				reason: jobMatches.reason,
				applyRecipient: jobMatches.applyRecipient,
				applyAction: jobMatches.applyAction,
				createdAt: jobMatches.createdAt,
				jobId: jobs.publicId,
				title: jobs.title,
				company: jobs.company,
				location: jobs.location,
				jobType: jobs.jobType,
				compensation: jobs.compensation
			})
			.from(jobMatches)
			.innerJoin(jobs, eq(jobMatches.jobId, jobs.id))
			.where(where)
			.orderBy(desc(jobMatches.score), desc(jobMatches.createdAt))
			.limit(PAGE_SIZE)
			.offset((page - 1) * PAGE_SIZE),
		db.select({ count: sql<number>`count(*)::int` }).from(jobMatches).where(where),
		db
			.select({ status: jobMatches.status, count: sql<number>`count(*)::int` })
			.from(jobMatches)
			.where(userFilter)
			.groupBy(jobMatches.status)
	]);

	const counts = new Map(statusRows.map((row) => [row.status, row.count]));
	const total = totalRows[0]?.count ?? 0;

	return {
		status,
		page,
		pages: Math.max(1, Math.ceil(total / PAGE_SIZE)),
		total,
		counts: {
			active: ACTIVE_STATUSES.reduce((sum, key) => sum + (counts.get(key) ?? 0), 0),
			all: statusRows.reduce((sum, row) => sum + row.count, 0),
			matched: counts.get('matched') ?? 0,
			generated: counts.get('generated') ?? 0,
			applied: counts.get('applied') ?? 0,
			waiting: counts.get('waiting') ?? 0,
			rejected: counts.get('rejected') ?? 0
		},
		matches: rows.map((row) => ({
			id: row.matchId,
			jobId: row.jobId,
			status: row.status,
			score: row.score,
			summary: publicSummary(row.reason),
			recipient: row.applyRecipient,
			action: row.applyAction,
			createdAt: row.createdAt,
			title: row.title ?? 'Untitled role',
			company: row.company ?? 'Employer',
			location: row.location ?? 'Zimbabwe',
			type: row.jobType,
			compensation: row.compensation
		}))
	};
};
