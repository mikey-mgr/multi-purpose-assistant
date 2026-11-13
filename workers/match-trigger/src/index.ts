type Env = {
	MATCH_TRIGGER_SECRET: string;
	MATCHER_URL: string;
	NOTIFY_URL: string;
};

function equal(a: string, b: string): boolean {
	if (a.length !== b.length) return false;
	let mismatch = 0;
	for (let i = 0; i < a.length; i += 1) mismatch |= a.charCodeAt(i) ^ b.charCodeAt(i);
	return mismatch === 0;
}

export default {
	async fetch(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
		if (request.method !== 'POST') {
			return Response.json({ error: 'Method not allowed' }, { status: 405 });
		}
		const supplied = request.headers.get('x-match-trigger-secret') ?? '';
		if (!env.MATCH_TRIGGER_SECRET || !equal(supplied, env.MATCH_TRIGGER_SECRET)) {
			return Response.json({ error: 'Unauthorized' }, { status: 401 });
		}
		if (!env.MATCHER_URL) {
			return Response.json({ error: 'MATCHER_URL is not configured' }, { status: 503 });
		}

		const body = await request.text();
		let webUserId = '';
		try {
			const parsed = JSON.parse(body) as { web_user_id?: string; user_id?: string };
			webUserId = parsed.web_user_id || parsed.user_id || '';
		} catch {
			return Response.json({ error: 'Invalid JSON' }, { status: 400 });
		}

		const run = fetch(env.MATCHER_URL, {
			method: 'POST',
			headers: {
				'Content-Type': 'application/json',
				'x-match-trigger-secret': env.MATCH_TRIGGER_SECRET
			},
			body
		})
			.then(async (response) => {
				if (!response.ok) {
					throw new Error(`Matcher returned ${response.status}`);
				}
				await response.json();
				if (env.NOTIFY_URL && webUserId) {
					await fetch(env.NOTIFY_URL, {
						method: 'POST',
						headers: {
							'Content-Type': 'application/json',
							'x-match-trigger-secret': env.MATCH_TRIGGER_SECRET
						},
						body: JSON.stringify({ user_id: webUserId })
					});
				}
			})
			.catch((error) => console.error('Matcher run failed', error));

		ctx.waitUntil(run);
		return Response.json({ status: 'accepted' }, { status: 202 });
	}
};
