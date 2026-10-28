import { json } from '@sveltejs/kit';
import { and, eq } from 'drizzle-orm';
import type { RequestHandler } from './$types';
import { decodedBase64Size } from '../../../../../lib/server/application-kit';
import { getDb } from '../../../../../lib/server/db';
import { applicationKits, oauthAccounts } from '../../../../../lib/server/db/schema';
import { composeLinks } from '../../../../../lib/server/mime';
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

	const limit = await rateLimit(rateLimitKey(event, 'applications:kit'), 120, 60);
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

	const gmail = await db
		.select({ id: oauthAccounts.id, email: oauthAccounts.email })
		.from(oauthAccounts)
		.where(
			and(
				eq(oauthAccounts.userId, event.locals.user.id),
				eq(oauthAccounts.provider, 'gmail')
			)
		)
		.limit(1);

	const row = kit[0];
	return json(
		{
			id: row.id,
			jobId: row.jobId,
			jobTitle: row.jobTitle,
			company: row.company,
			recipient: row.recipient,
			subject: row.subject,
			body: row.body,
			attachments: row.attachments.map((attachment) => ({
				name: attachment.name,
				mime: attachment.mime,
				bytes: decodedBase64Size(attachment.contentBase64)
			})),
			composeLinks: composeLinks(row.recipient, row.subject, row.body),
			emlPath: `/api/applications/${row.id}/kit.eml`,
			gmailConnected: Boolean(gmail[0]),
			gmailEmail: gmail[0]?.email ?? null
		},
		{ headers: { 'Cache-Control': 'no-store' } }
	);
};
