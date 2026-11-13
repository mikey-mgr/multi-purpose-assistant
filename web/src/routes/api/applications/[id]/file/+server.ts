import { json } from '@sveltejs/kit';
import { and, eq } from 'drizzle-orm';
import type { RequestHandler } from './$types';
import { getDb } from '../../../../../lib/server/db';
import { applicationKits } from '../../../../../lib/server/db/schema';
import { rateLimit, rateLimitKey, tooManyRequests } from '../../../../../lib/server/rate-limit';

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export const GET: RequestHandler = async (event) => {
	if (!event.locals.user) {
		return json({ error: 'Unauthorized' }, { status: 401 });
	}
	if (!UUID_RE.test(event.params.id)) {
		return json({ error: 'Not found' }, { status: 404 });
	}

	const limit = await rateLimit(rateLimitKey(event, 'applications:file'), 120, 60);
	if (!limit.allowed) return tooManyRequests(limit);

	const index = Number(event.url.searchParams.get('index') ?? '0');
	if (!Number.isInteger(index) || index < 0) {
		return json({ error: 'Invalid attachment index' }, { status: 400 });
	}

	const db = await getDb();
	const rows = await db
		.select({ attachments: applicationKits.attachments })
		.from(applicationKits)
		.where(
			and(eq(applicationKits.id, event.params.id), eq(applicationKits.userId, event.locals.user.id))
		)
		.limit(1);

	const attachment = rows[0]?.attachments[index];
	if (!attachment) {
		return json({ error: 'Attachment not found' }, { status: 404 });
	}

	const binary = atob(attachment.contentBase64);
	const bytes = new Uint8Array(binary.length);
	for (let offset = 0; offset < binary.length; offset += 1) {
		bytes[offset] = binary.charCodeAt(offset);
	}

	const fallback = attachment.name.replace(/[^\x20-\x7e]+/g, '_').replace(/["\\]/g, '_');
	const headers = new Headers();
	headers.set('Content-Type', attachment.mime || 'application/octet-stream');
	headers.set(
		'Content-Disposition',
		`attachment; filename="${fallback}"; filename*=UTF-8''${encodeURIComponent(attachment.name)}`
	);
	headers.set('Cache-Control', 'private, max-age=60');
	return new Response(bytes, { headers });
};
