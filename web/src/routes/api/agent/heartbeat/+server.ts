import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { authenticateAgent } from '../../../../lib/server/agent-auth';

export const POST: RequestHandler = async (event) => {
	const agent = await authenticateAgent(event);
	if (!agent) {
		return json({ error: 'Unauthorized' }, { status: 401 });
	}

	return json({
		ok: true,
		agentId: agent.id,
		kind: agent.kind,
		serverTime: new Date().toISOString()
	});
};
