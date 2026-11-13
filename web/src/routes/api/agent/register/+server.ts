import { json } from '@sveltejs/kit';
import { z } from 'zod';
import type { RequestHandler } from './$types';
import { bootstrapAuthorized, createAgent, isAgentKind } from '../../../../lib/server/agent-auth';
import { rateLimit } from '../../../../lib/server/rate-limit';

const input = z
	.object({
		name: z.string().trim().min(2).max(80),
		kind: z.enum(['scraper', 'apply', 'both'])
	})
	.strict();

export const POST: RequestHandler = async (event) => {
	// A signed-in user registers their own agent. The bootstrap secret is kept for
	// owner-run scrapers only and never binds an agent to a user account.
	const boundUserId = event.locals.user?.id ?? null;
	if (!boundUserId && !bootstrapAuthorized(event)) {
		return json({ error: 'Unauthorized' }, { status: 401 });
	}

	const limit = await rateLimit(
		boundUserId ? `agent-register:${boundUserId}` : `agent-register:${event.getClientAddress()}`,
		10,
		3600
	);
	if (!limit.allowed) {
		return json({ error: 'Too many requests' }, { status: 429 });
	}

	let body: unknown;
	try {
		body = await event.request.json();
	} catch {
		return json({ error: 'Invalid JSON body' }, { status: 400 });
	}

	const parsed = input.safeParse(body);
	if (!parsed.success || !isAgentKind(parsed.data.kind)) {
		return json({ error: 'Invalid agent registration' }, { status: 400 });
	}

	// An unbound agent may only scrape; apply agents must belong to a user.
	if (!boundUserId && parsed.data.kind !== 'scraper') {
		return json({ error: 'Apply agents must be registered by a signed-in user' }, { status: 403 });
	}

	const created = await createAgent(parsed.data.name, parsed.data.kind, boundUserId);
	return json(
		{
			agentId: created.agent?.id,
			agentKey: created.agentKey,
			name: created.agent?.name,
			kind: created.agent?.kind
		},
		{ status: 201 }
	);
};
