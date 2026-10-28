import { redirect } from '@sveltejs/kit';
import { and, eq } from 'drizzle-orm';
import { getDb } from '../../lib/server/db';
import { oauthAccounts, whatsappPilot } from '../../lib/server/db/schema';

export const load = async ({ locals, url }) => {
	if (!locals.user) redirect(303, '/login');

	const db = await getDb();
	const gmail = await db
		.select()
		.from(oauthAccounts)
		.where(
			and(
				eq(oauthAccounts.userId, locals.user.id),
				eq(oauthAccounts.provider, 'gmail')
			)
		)
		.limit(1);

	const pilot = await db
		.select()
		.from(whatsappPilot)
		.where(eq(whatsappPilot.userId, locals.user.id))
		.limit(1);

	return {
		user: locals.user,
		gmail: gmail[0]
			? { connected: true, email: gmail[0].email }
			: { connected: false, email: null },
		whatsapp: pilot[0]
			? { joined: true, slot: pilot[0].slot, status: pilot[0].status, phone: pilot[0].phone }
			: { joined: false, slot: null, status: null, phone: null },
		gmailStatus: url.searchParams.get('gmail')
	};
};
