import { redirect } from '@sveltejs/kit';
import { eq } from 'drizzle-orm';
import { getDb } from '../../lib/server/db';
import { profiles, whatsappPilot } from '../../lib/server/db/schema';

export const load = async ({ locals }) => {
	if (!locals.user) redirect(303, '/login');

	const db = await getDb();
	const pilot = await db
		.select()
		.from(whatsappPilot)
		.where(eq(whatsappPilot.userId, locals.user.id))
		.limit(1);

	const profile = await db
		.select({
			phone: profiles.phone,
			linkedinUrl: profiles.linkedinUrl,
			cvTemplate: profiles.cvTemplate
		})
		.from(profiles)
		.where(eq(profiles.userId, locals.user.id))
		.limit(1);

	return {
		user: locals.user,
		profile: profile[0] ?? { phone: null, linkedinUrl: null, cvTemplate: 'harvard' as const },
		whatsapp: pilot[0]
			? { joined: true, slot: pilot[0].slot, status: pilot[0].status, phone: pilot[0].phone }
			: { joined: false, slot: null, status: null, phone: null }
	};
};
