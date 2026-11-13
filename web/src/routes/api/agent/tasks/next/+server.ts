import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { authenticateAgent, agentRateKey } from '../../../../../lib/server/agent-auth';
import { claimAgentTask } from '../../../../../lib/server/agent-tasks';
import { rateLimit, tooManyRequests } from '../../../../../lib/server/rate-limit';

export const GET: RequestHandler = async (event) => {
	const agent = await authenticateAgent(event, ['scraper', 'apply', 'both']);
	if (!agent) {
		return json({ error: 'Unauthorized' }, { status: 401 });
	}

	const kind = event.url.searchParams.get('kind');
	if (kind !== 'scrape' && kind !== 'apply') {
		return json({ error: 'kind must be scrape or apply' }, { status: 400 });
	}
	const requiredKind = kind === 'scrape' ? 'scraper' : 'apply';
	if (agent.kind !== 'both' && agent.kind !== requiredKind) {
		return json({ error: 'Agent is not allowed to claim this task kind' }, { status: 403 });
	}

	const limit = await rateLimit(agentRateKey(agent.id, 'tasks:next'), 300, 60);
	if (!limit.allowed) return tooManyRequests(limit);

	const task = await claimAgentTask(agent.id, kind, agent.userId ?? null);
	return json({ task }, { headers: { 'Cache-Control': 'no-store' } });
};
