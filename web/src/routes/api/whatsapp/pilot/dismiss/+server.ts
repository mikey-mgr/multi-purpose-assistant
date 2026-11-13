import { json } from '@sveltejs/kit';
import { eq } from 'drizzle-orm';
import type { RequestHandler } from './$types';
import { getDb } from '../../../../../lib/server/db';
import { profiles } from '../../../../../lib/server/db/schema';

export const POST: RequestHandler = async (event) => {
	if (!event.locals.user) {
		return json({ error: 'Unauthorized' }, { status: 401 });
	}

	const db = await getDb();
	await db
		.update(profiles)
		.set({ whatsappPromptDismissedAt: new Date() })
		.where(eq(profiles.userId, event.locals.user.id));

	return json({ ok: true });
};
