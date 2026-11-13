import { redirect } from '@sveltejs/kit';
import { and, desc, eq, sql } from 'drizzle-orm';
import { getDb } from '../../lib/server/db';
import { documents, jobs, userFiles } from '../../lib/server/db/schema';

const PAGE_SIZE = 30;
const TYPES = ['resume', 'cover_letter', 'interview_prep'];

export const load = async ({ locals, url }) => {
	if (!locals.user) redirect(303, '/login');

	const requested = url.searchParams.get('type') ?? 'all';
	const type = requested === 'all' || TYPES.includes(requested) ? requested : 'all';
	const page = Math.max(1, Number(url.searchParams.get('page') ?? 1) || 1);
	const userFilter = eq(documents.userId, locals.user.id);
	const where = type === 'all' ? userFilter : and(userFilter, eq(documents.documentType, type));

	const db = await getDb();
	const [rows, totalRows, typeRows, fileRows] = await Promise.all([
		db
			.select({
				id: documents.id,
				type: documents.documentType,
				model: documents.model,
				createdAt: documents.createdAt,
				jobId: jobs.publicId,
				jobTitle: jobs.title,
				company: jobs.company
			})
			.from(documents)
			.leftJoin(jobs, eq(documents.jobId, jobs.id))
			.where(where)
			.orderBy(desc(documents.createdAt))
			.limit(PAGE_SIZE)
			.offset((page - 1) * PAGE_SIZE),
		db.select({ count: sql<number>`count(*)::int` }).from(documents).where(where),
		db
			.select({ type: documents.documentType, count: sql<number>`count(*)::int` })
			.from(documents)
			.where(userFilter)
			.groupBy(documents.documentType),
		db
			.select()
			.from(userFiles)
			.where(eq(userFiles.userId, locals.user.id))
			.orderBy(desc(userFiles.createdAt))
			.limit(20)
	]);

	const counts = new Map(typeRows.map((row) => [row.type, row.count]));
	const total = totalRows[0]?.count ?? 0;

	return {
		type,
		page,
		pages: Math.max(1, Math.ceil(total / PAGE_SIZE)),
		total,
		counts: {
			all: typeRows.reduce((sum, row) => sum + row.count, 0),
			resume: counts.get('resume') ?? 0,
			cover_letter: counts.get('cover_letter') ?? 0,
			interview_prep: counts.get('interview_prep') ?? 0
		},
		documents: rows.map((row) => ({
			id: row.id,
			type: row.type,
			model: row.model,
			createdAt: row.createdAt,
			jobId: row.jobId,
			jobTitle: row.jobTitle,
			company: row.company
		})),
		files: fileRows.map((row) => ({
			id: row.id,
			filename: row.filename,
			contentType: row.contentType,
			purpose: row.purpose,
			size: row.size,
			createdAt: row.createdAt
		}))
	};
};
