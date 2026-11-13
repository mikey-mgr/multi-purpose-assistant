import { redirect } from '@sveltejs/kit';
import { envValue } from '../../../lib/server/env';
import { getOwnerAnalytics } from '../../../lib/server/insights';

export const load = async ({ locals }) => {
	if (!locals.user) redirect(303, '/login');

	// Internal diagnostics: owner only.
	const ownerLegacyId = envValue('APPLY_AGENT_LEGACY_USER_ID');
	if (!ownerLegacyId || locals.user.id !== ownerLegacyId) {
		redirect(303, '/insights');
	}

	const analytics = await getOwnerAnalytics();
	return { analytics };
};
