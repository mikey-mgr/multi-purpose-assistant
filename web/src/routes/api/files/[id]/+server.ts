import { json } from '@sveltejs/kit';
import { and, eq } from 'drizzle-orm';
import type { RequestHandler } from './$types';
import { getDb } from '../../../../lib/server/db';
import { userFiles } from '../../../../lib/server/db/schema';
import { deleteFile, getFile } from '../../../../lib/server/file-storage';
import { rateLimit, rateLimitKey, tooManyRequests } from '../../../../lib/server/rate-limit';

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

async function ownedFile(event: Parameters<RequestHandler>[0]) {
	if (!event.locals.user) return null;
	if (!UUID_RE.test(event.params.id)) return null;
	const db = await getDb();
	const rows = await db
		.select()
		.from(userFiles)
		.where(and(eq(userFiles.id, event.params.id), eq(userFiles.userId, event.locals.user.id)))
		.limit(1);
	return rows[0] ?? null;
}

export const GET: RequestHandler = async (event) => {
	if (!event.locals.user) {
		return json({ error: 'Unauthorized' }, { status: 401 });
	}

	const limit = await rateLimit(rateLimitKey(event, 'files:download'), 120, 60);
	if (!limit.allowed) return tooManyRequests(limit);

	const row = await ownedFile(event);
	if (!row) return json({ error: 'Not found' }, { status: 404 });

	const object = await getFile(row.r2Key);
	if (!object) return json({ error: 'File not found in storage' }, { status: 404 });

	const headers = new Headers();
	headers.set('Content-Type', row.contentType);
	headers.set('Content-Length', String(row.size));
	headers.set('Cache-Control', 'private, max-age=300');
	headers.set(
		'Content-Disposition',
		`attachment; filename*=UTF-8''${encodeURIComponent(row.filename)}`
	);
	const etag = object.headers.get('etag');
	if (etag) headers.set('ETag', etag);

	return new Response(object.body, { headers });
};

export const DELETE: RequestHandler = async (event) => {
	if (!event.locals.user) {
		return json({ error: 'Unauthorized' }, { status: 401 });
	}

	const row = await ownedFile(event);
	if (!row) return json({ error: 'Not found' }, { status: 404 });

	await deleteFile(row.r2Key);

	const db = await getDb();
	await db
		.delete(userFiles)
		.where(and(eq(userFiles.id, row.id), eq(userFiles.userId, event.locals.user.id)));

	return json({ ok: true });
};
