import { json } from '@sveltejs/kit';
import { z } from 'zod';
import type { RequestHandler } from './$types';
import { bootstrapAuthorized } from '../../../../lib/server/agent-auth';
import { createAgentTask } from '../../../../lib/server/agent-tasks';

const input = z
	.object({
		site_names: z.array(z.string().max(50)).max(10).optional(),
		max_pages: z.number().int().min(1).max(10).optional(),
		max_jobs: z.number().int().min(1).max(200).optional()
	})
	.strict()
	.default({});

export const POST: RequestHandler = async (event) => {
	if (!bootstrapAuthorized(event)) {
		return json({ error: 'Unauthorized' }, { status: 401 });
	}

	let body: unknown = {};
	try {
		const text = await event.request.text();
		body = text ? JSON.parse(text) : {};
	} catch {
		return json({ error: 'Invalid JSON body' }, { status: 400 });
	}

	const parsed = input.safeParse(body);
	if (!parsed.success) {
		return json({ error: 'Invalid scrape task', issues: parsed.error.flatten() }, { status: 400 });
	}

	const task = await createAgentTask('scrape', {
		site_names: parsed.data.site_names ?? null,
		max_pages: parsed.data.max_pages ?? null,
		max_jobs: parsed.data.max_jobs ?? null
	});
	return json({ status: 'queued', task }, { status: 202 });
};
