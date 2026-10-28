import { json } from '@sveltejs/kit';
import { and, eq } from 'drizzle-orm';
import type { RequestHandler } from './$types';
import {
	buildApplicationEml,
	safeFilename
} from '../../../../../lib/server/application-kit';
import { getDb } from '../../../../../lib/server/db';
import { applicationKits } from '../../../../../lib/server/db/schema';
import { rateLimit, rateLimitKey, tooManyRequests } from '../../../../../lib/server/rate-limit';

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export const GET: RequestHandler = async (event) => {
	if (!event.locals.user) {
		return json({ error: 'Unauthorized' }, { status: 401 });
	}

	const id = event.params.id;
	if (!UUID_RE.test(id)) {
		return json({ error: 'Not found' }, { status: 404 });
	}

	const limit = await rateLimit(rateLimitKey(event, 'applications:eml'), 30, 60);
	if (!limit.allowed) return tooManyRequests(limit);

	const db = await getDb();
	const kit = await db
		.select()
		.from(applicationKits)
		.where(and(eq(applicationKits.id, id), eq(applicationKits.userId, event.locals.user.id)))
		.limit(1);

	if (!kit[0]) {
		return json({ error: 'Not found' }, { status: 404 });
	}

	const row = kit[0];
	const eml = buildApplicationEml({
		recipient: row.recipient,
		subject: row.subject,
		body: row.body,
		attachments: row.attachments
	});
	const filename = `${safeFilename(`${row.company ?? 'application'}-${row.jobTitle ?? 'role'}`)}.eml`;

	return new Response(eml, {
		headers: {
			'Content-Type': 'message/rfc822',
			'Content-Disposition': `attachment; filename="${filename}"`,
			'Cache-Control': 'no-store'
		}
	});
};
