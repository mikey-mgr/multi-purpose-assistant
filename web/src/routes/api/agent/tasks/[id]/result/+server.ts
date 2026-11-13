import { json } from '@sveltejs/kit';
import { and, eq } from 'drizzle-orm';
import { z } from 'zod';
import type { RequestHandler } from './$types';
import { authenticateAgent, agentRateKey } from '../../../../../../lib/server/agent-auth';
import { completeAgentTask, upsertAgentJobs } from '../../../../../../lib/server/agent-tasks';
import { getDb } from '../../../../../../lib/server/db';
import { agentTasks } from '../../../../../../lib/server/db/schema';
import { rateLimit, tooManyRequests } from '../../../../../../lib/server/rate-limit';

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

const input = z
	.object({
		status: z.enum(['completed', 'failed']),
		result: z.record(z.string(), z.unknown()).default({})
	})
	.strict();

export const POST: RequestHandler = async (event) => {
	const agent = await authenticateAgent(event, ['scraper', 'apply', 'both']);
	if (!agent) {
		return json({ error: 'Unauthorized' }, { status: 401 });
	}
	if (!UUID_RE.test(event.params.id)) {
		return json({ error: 'Not found' }, { status: 404 });
	}

	const limit = await rateLimit(agentRateKey(agent.id, 'tasks:result'), 120, 60);
	if (!limit.allowed) return tooManyRequests(limit);

	let body: unknown;
	try {
		body = await event.request.json();
	} catch {
		return json({ error: 'Invalid JSON body' }, { status: 400 });
	}

	const parsed = input.safeParse(body);
	if (!parsed.success) {
		return json({ error: 'Invalid task result', issues: parsed.error.flatten() }, { status: 400 });
	}

	const db = await getDb();
	const task = await db
		.select()
		.from(agentTasks)
		.where(and(eq(agentTasks.id, event.params.id), eq(agentTasks.agentId, agent.id)))
		.limit(1);

	if (!task[0]) {
		return json({ error: 'Task not found' }, { status: 404 });
	}
	if (task[0].status !== 'claimed') {
		return json({ error: `Task is already ${task[0].status}` }, { status: 409 });
	}

	let jobsResult: { inserted: number; skipped: number; error: string | null } | null = null;
	if (parsed.data.status === 'completed' && task[0].kind === 'scrape') {
		jobsResult = await upsertAgentJobs(parsed.data.result.jobs);
		if (jobsResult.error) {
			return json({ error: jobsResult.error }, { status: 400 });
		}
	}

	const completed = await completeAgentTask(
		task[0].id,
		agent.id,
		parsed.data.status,
		parsed.data.result
	);

	return json({
		ok: true,
		taskId: completed?.id,
		status: completed?.status,
		jobs: jobsResult
	});
};
