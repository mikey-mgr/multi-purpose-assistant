import { error, redirect } from '@sveltejs/kit';
import { eq } from 'drizzle-orm';
import { getDb } from '../../../lib/server/db';
import { jobs } from '../../../lib/server/db/schema';
import { publicSummary } from '../../../lib/server/sanitize';

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export const load = async ({ locals, params }) => {
	if (!locals.user) redirect(303, '/login');
	if (!UUID_RE.test(params.id)) error(404, 'Job not found');

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
		.where(eq(jobs.publicId, params.id))
		.limit(1);

	if (!row[0]) error(404, 'Job not found');

	return {
		job: {
			id: row[0].publicId,
			title: row[0].title ?? 'Untitled role',
			company: row[0].company ?? 'Employer',
			location: row[0].location ?? 'Zimbabwe',
			type: row[0].jobType,
			compensation: row[0].compensation,
			datePosted: row[0].datePosted,
			expires: row[0].expires,
			category: row[0].category,
			remote: row[0].remote,
			summary: publicSummary(row[0].description, 1200),
			applyInstructions: row[0].applyInstructions
				? publicSummary(row[0].applyInstructions, 1200)
				: null
		}
	};
};
