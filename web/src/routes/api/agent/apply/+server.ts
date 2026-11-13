import { json } from '@sveltejs/kit';
import { z } from 'zod';
import type { RequestHandler } from './$types';
import { authenticateAgent, bootstrapAuthorized } from '../../../../lib/server/agent-auth';
import { createAgentTask } from '../../../../lib/server/agent-tasks';

const input = z
	.object({
		legacy_user_id: z.string().uuid(),
		limit: z.number().int().min(1).max(50).default(10),
		dry_run: z.boolean().default(false),
		kit_id: z.string().uuid().optional(),
		match_id: z.string().uuid().optional(),
		test_recipient: z.string().email().max(250).optional()
	})
	.strict();

export const POST: RequestHandler = async (event) => {
	let body: unknown;
	try {
		body = await event.request.json();
	} catch {
		return json({ error: 'Invalid JSON body' }, { status: 400 });
	}

	const parsed = input.safeParse(body);
	if (!parsed.success) {
		return json({ error: 'Invalid apply task', issues: parsed.error.flatten() }, { status: 400 });
	}

	// Either an agent bound to this account, or the server-side bootstrap secret
	// which stays on the owner's own infrastructure. An unbound agent must never
	// be able to queue a send for someone else.
	const agent = await authenticateAgent(event, ['apply', 'both']);
	if (agent) {
		if (!agent.userId || agent.userId !== parsed.data.legacy_user_id) {
			return json({ error: 'Forbidden' }, { status: 403 });
		}
	} else if (!bootstrapAuthorized(event)) {
		return json({ error: 'Unauthorized' }, { status: 401 });
	}

	const task = await createAgentTask('apply', parsed.data);
	return json({ status: 'queued', task }, { status: 202 });
};
