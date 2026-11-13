import { envValue } from './env';

function service(): { base: string; secret: string } | null {
	const base = envValue('FILES_SERVICE_URL');
	const secret = envValue('FILES_SERVICE_SECRET');
	if (!base || !secret) return null;
	return { base: base.replace(/\/$/, ''), secret };
}

export async function putFile(key: string, file: File): Promise<boolean> {
	const config = service();
	if (!config) return false;
	const body = new FormData();
	body.append('file', file);
	const response = await fetch(`${config.base}/upload`, {
		method: 'POST',
		headers: {
			'x-files-secret': config.secret,
			'x-file-key': key
		},
		body
	});
	return response.ok;
}

export async function getFile(key: string): Promise<Response | null> {
	const config = service();
	if (!config) return null;
	const response = await fetch(
		`${config.base}/object?key=${encodeURIComponent(key)}`,
		{ headers: { 'x-files-secret': config.secret } }
	);
	return response.ok ? response : null;
}

export async function extractResumeText(file: File): Promise<string | null> {
	const base = envValue('MATCHER_EXTRACT_URL');
	const secret = envValue('MATCH_TRIGGER_SECRET');
	if (!base || !secret) return null;
	const body = new FormData();
	body.append('file', file);
	try {
		const response = await fetch(base, {
			method: 'POST',
			headers: { 'x-match-trigger-secret': secret },
			body
		});
		if (!response.ok) return null;
		const payload = (await response.json()) as { text?: string };
		return payload.text?.trim() || null;
	} catch {
		return null;
	}
}

export async function deleteFile(key: string): Promise<void> {
	const config = service();
	if (!config) return;
	await fetch(`${config.base}/object?key=${encodeURIComponent(key)}`, {
		method: 'DELETE',
		headers: { 'x-files-secret': config.secret }
	});
}
