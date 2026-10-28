import { json } from '@sveltejs/kit';
import { and, eq } from 'drizzle-orm';
import type { RequestHandler } from './$types';
import { decryptSecret } from '../../../../../lib/server/crypto';
import { getDb } from '../../../../../lib/server/db';
import { applicationKits, oauthAccounts } from '../../../../../lib/server/db/schema';
import {
	createGmailDraft,
	gmailDraftLink,
	isGmailMock
} from '../../../../../lib/server/gmail';
import { rateLimit, rateLimitKey, tooManyRequests } from '../../../../../lib/server/rate-limit';

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export const POST: RequestHandler = async (event) => {
	if (!event.locals.user) {
		return json({ error: 'Unauthorized' }, { status: 401 });
	}

	const id = event.params.id;
	if (!UUID_RE.test(id)) {
		return json({ error: 'Not found' }, { status: 404 });
	}

	const limit = await rateLimit(rateLimitKey(event, 'applications:gmail-draft'), 20, 3600);
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
		.select()
		.from(oauthAccounts)
		.where(
			and(
				eq(oauthAccounts.userId, event.locals.user.id),
				eq(oauthAccounts.provider, 'gmail')
			)
		)
		.limit(1);

	if (!gmail[0]) {
		return json(
			{
				error: 'Gmail is not connected',
				connectUrl: '/api/integrations/gmail/connect'
			},
			{ status: 409 }
		);
	}

	try {
		const refreshToken = await decryptSecret(
			gmail[0].encryptedRefreshToken,
			gmail[0].iv
		);
		const row = kit[0];
		const draft = await createGmailDraft({
			refreshToken,
			to: row.recipient,
			subject: row.subject,
			body: row.body,
			attachments: row.attachments
		});

		return json({
			draftId: draft.draftId,
			messageId: draft.messageId,
			mock: draft.mock || isGmailMock(),
			draftUrl: gmailDraftLink()
		});
	} catch {
		return json({ error: 'Could not create the Gmail draft' }, { status: 502 });
	}
};
