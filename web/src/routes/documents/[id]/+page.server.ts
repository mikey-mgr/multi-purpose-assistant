import { error, redirect } from '@sveltejs/kit';
import { and, eq } from 'drizzle-orm';
import { getDb } from '../../../lib/server/db';
import { documents, jobs } from '../../../lib/server/db/schema';

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export const load = async ({ locals, params }) => {
	if (!locals.user) redirect(303, '/login');
	if (!UUID_RE.test(params.id)) error(404, 'Document not found');

	const db = await getDb();
	const row = await db
		.select({
			id: documents.id,
			type: documents.documentType,
			content: documents.content,
			pdfPath: documents.pdfPath,
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
		.where(and(eq(documents.id, params.id), eq(documents.userId, locals.user.id)))
		.limit(1);

	if (!row[0]) error(404, 'Document not found');

	return {
		document: {
			id: row[0].id,
			type: row[0].type,
			content: row[0].content,
			pdfPath: row[0].pdfPath,
			rendercvYaml: row[0].rendercvYaml,
			promptName: row[0].promptName,
			model: row[0].model,
			tokensUsed: row[0].tokensUsed,
			createdAt: row[0].createdAt,
			jobId: row[0].jobId,
			jobTitle: row[0].jobTitle,
			company: row[0].company
		}
	};
};
