type Env = {
	FILES: R2Bucket;
	FILES_SECRET: string;
};

const MAX_BYTES = 15 * 1024 * 1024;

function equal(a: string, b: string): boolean {
	if (a.length !== b.length) return false;
	let mismatch = 0;
	for (let i = 0; i < a.length; i += 1) mismatch |= a.charCodeAt(i) ^ b.charCodeAt(i);
	return mismatch === 0;
}

function authorized(request: Request, env: Env): boolean {
	const supplied = request.headers.get('x-files-secret') ?? '';
	return Boolean(env.FILES_SECRET) && equal(supplied, env.FILES_SECRET);
}

export default {
	async fetch(request: Request, env: Env): Promise<Response> {
		if (!authorized(request, env)) {
			return Response.json({ error: 'Unauthorized' }, { status: 401 });
		}

		const url = new URL(request.url);

		if (url.pathname === '/upload' && request.method === 'POST') {
			const key = request.headers.get('x-file-key');
			if (!key || !key.startsWith('users/') || key.includes('..')) {
				return Response.json({ error: 'Invalid key' }, { status: 400 });
			}
			let form: FormData;
			try {
				form = await request.formData();
			} catch {
				return Response.json({ error: 'Invalid upload' }, { status: 400 });
			}
			const file = form.get('file');
			if (!(file instanceof File) || file.size === 0) {
				return Response.json({ error: 'Missing file' }, { status: 400 });
			}
			if (file.size > MAX_BYTES) {
				return Response.json({ error: 'File too large' }, { status: 413 });
			}
			await env.FILES.put(key, file.stream(), {
				httpMetadata: { contentType: file.type || 'application/octet-stream' }
			});
			return Response.json({ ok: true, key });
		}

		if (url.pathname === '/object' && request.method === 'GET') {
			const key = url.searchParams.get('key');
			if (!key || !key.startsWith('users/') || key.includes('..')) {
				return Response.json({ error: 'Invalid key' }, { status: 400 });
			}
			const object = await env.FILES.get(key);
			if (!object) return Response.json({ error: 'Not found' }, { status: 404 });
			const headers = new Headers();
			headers.set('Content-Type', object.httpMetadata?.contentType ?? 'application/octet-stream');
			if (object.httpEtag) headers.set('ETag', object.httpEtag);
			return new Response(object.body, { headers });
		}

		if (url.pathname === '/object' && request.method === 'DELETE') {
			const key = url.searchParams.get('key');
			if (!key || !key.startsWith('users/') || key.includes('..')) {
				return Response.json({ error: 'Invalid key' }, { status: 400 });
			}
			await env.FILES.delete(key);
			return Response.json({ ok: true });
		}

		return Response.json({ error: 'Not found' }, { status: 404 });
	}
};
