import { redirect } from '@sveltejs/kit';
import { desc, eq } from 'drizzle-orm';
import { decodedBase64Size } from '../../lib/server/application-kit';
import { getDb } from '../../lib/server/db';
import { applicationKits } from '../../lib/server/db/schema';

export const load = async ({ locals }) => {
	if (!locals.user) redirect(303, '/login');

	const db = await getDb();
	const rows = await db
		.select()
		.from(applicationKits)
		.where(eq(applicationKits.userId, locals.user.id))
		.orderBy(desc(applicationKits.createdAt))
		.limit(50);

	return {
		kits: rows.map((row) => ({
			id: row.id,
			jobId: row.jobId,
			jobTitle: row.jobTitle ?? 'Untitled role',
			company: row.company ?? 'Employer',
			recipient: row.recipient,
			subject: row.subject,
			createdAt: row.createdAt,
			merged: row.metadata?.merged ?? false,
			blockers: row.metadata?.blockers ?? [],
			attachments: row.attachments.map((attachment, index) => ({
				index,
				name: attachment.name,
				mime: attachment.mime,
				bytes: decodedBase64Size(attachment.contentBase64)
			}))
		}))
	};
};
