import { redirect } from '@sveltejs/kit';
import { getMarketSnapshot } from '../../lib/server/insights';

export const load = async ({ locals }) => {
	if (!locals.user) redirect(303, '/login');
	const market = await getMarketSnapshot();
	return { user: locals.user, market };
};
