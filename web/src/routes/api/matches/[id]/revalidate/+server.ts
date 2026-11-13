import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { rateLimit, rateLimitKey, tooManyRequests } from '../../../../../lib/server/rate-limit';
import { rebuildApplication } from '../../../../../lib/server/resume/rebuild';

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export const POST: RequestHandler = async (event) => {
	if (!event.locals.user) {
		return json({ error: 'Unauthorized' }, { status: 401 });
	}
	if (!UUID_RE.test(event.params.id)) {
		return json({ error: 'Not found' }, { status: 404 });
	}

	const limit = await rateLimit(rateLimitKey(event, 'matches:revalidate'), 10, 300);
	if (!limit.allowed) return tooManyRequests(limit);

	const result = await rebuildApplication(event.params.id, event.locals.user.id);
	if (!result.ok) {
		return json({ error: result.error ?? 'Could not re-check this application' }, { status: 400 });
	}

	return json(result);
};
