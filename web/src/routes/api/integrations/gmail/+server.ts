import { json } from '@sveltejs/kit';
import { and, eq } from 'drizzle-orm';
import type { RequestHandler } from './$types';
import { getDb } from '../../../../lib/server/db';
import { oauthAccounts } from '../../../../lib/server/db/schema';

export const DELETE: RequestHandler = async (event) => {
	if (!event.locals.user) {
		return json({ error: 'Unauthorized' }, { status: 401 });
	}

	const db = await getDb();
	await db
		.delete(oauthAccounts)
		.where(
			and(eq(oauthAccounts.userId, event.locals.user.id), eq(oauthAccounts.provider, 'gmail'))
		);

	return json({ ok: true });
};
