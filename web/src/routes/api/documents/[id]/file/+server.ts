import { json } from '@sveltejs/kit';
import { and, eq } from 'drizzle-orm';
import type { RequestHandler } from './$types';
import { getDb } from '../../../../../lib/server/db';
import { documents } from '../../../../../lib/server/db/schema';
import { getFile } from '../../../../../lib/server/file-storage';
import { rateLimit, rateLimitKey, tooManyRequests } from '../../../../../lib/server/rate-limit';

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export const GET: RequestHandler = async (event) => {
	if (!event.locals.user) {
		return json({ error: 'Unauthorized' }, { status: 401 });
	}
	if (!UUID_RE.test(event.params.id)) {
		return json({ error: 'Not found' }, { status: 404 });
	}

	const limit = await rateLimit(rateLimitKey(event, 'documents:file'), 60, 60);
	if (!limit.allowed) return tooManyRequests(limit);

	const db = await getDb();
	const rows = await db
		.select({ filename: documents.documentType, pdfPath: documents.pdfPath })
		.from(documents)
		.where(and(eq(documents.id, event.params.id), eq(documents.userId, event.locals.user.id)))
		.limit(1);

	const row = rows[0];
	if (!row?.pdfPath) return json({ error: 'File not found' }, { status: 404 });
	const file = await getFile(row.pdfPath);
	if (!file) return json({ error: 'File not found in storage' }, { status: 404 });

	const keyName = decodeURIComponent(row.pdfPath.split('/').pop() ?? '');
	const filename =
		keyName
			.replace(
				/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}-/i,
				''
			)
			.replace(/(?<! )-(?! )/g, ' ')
			.replace(/\s{2,}/g, ' ')
			.trim() || `mukana-${row.filename}.pdf`;
	const extension = filename.toLowerCase().endsWith('.pdf')
		? 'pdf'
		: filename.toLowerCase().endsWith('.docx')
			? 'docx'
			: 'bin';
	const contentType =
		extension === 'pdf'
			? 'application/pdf'
			: extension === 'docx'
				? 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
				: 'application/octet-stream';
	const fallback = filename.replace(/[^\x20-\x7e]+/g, '_').replace(/["\\]/g, '_');
	const headers = new Headers();
	headers.set('Content-Type', contentType);
	headers.set(
		'Content-Disposition',
		`attachment; filename="${fallback}"; filename*=UTF-8''${encodeURIComponent(filename)}`
	);
	return new Response(file.body, { headers });
};
