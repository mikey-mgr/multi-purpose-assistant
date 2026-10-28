import { base64Url, randomToken } from './crypto';
import { envValue } from './env';
import { buildMimeMessage } from './mime';
import type { KitAttachment } from './db/schema';

const AUTH_URL = 'https://accounts.google.com/o/oauth2/v2/auth';
const TOKEN_URL = 'https://oauth2.googleapis.com/token';
const GMAIL_API = 'https://gmail.googleapis.com/gmail/v1/users/me';
const USERINFO_URL = 'https://www.googleapis.com/oauth2/v2/userinfo';

export const GMAIL_SCOPES = [
	'openid',
	'email',
	'https://www.googleapis.com/auth/gmail.compose'
];

export type GmailTokens = {
	accessToken: string;
	refreshToken: string | null;
	expiresIn: number;
	scope: string | null;
};

export function isGmailMock(): boolean {
	return envValue('GMAIL_MODE') !== 'live';
}

export function gmailConfigured(): boolean {
	if (isGmailMock()) return true;
	return Boolean(envValue('GOOGLE_CLIENT_ID') && envValue('GOOGLE_CLIENT_SECRET'));
}

function requireConfig() {
	const clientId = envValue('GOOGLE_CLIENT_ID');
	const clientSecret = envValue('GOOGLE_CLIENT_SECRET');
	const redirectUri = envValue('GOOGLE_REDIRECT_URI');
	if (!clientId || !clientSecret || !redirectUri) {
		throw new Error('Gmail OAuth is not configured');
	}
	return { clientId, clientSecret, redirectUri };
}

export function buildGmailAuthUrl(state: string): string {
	if (isGmailMock()) {
		const redirectUri = envValue('GOOGLE_REDIRECT_URI') ?? '';
		const url = new URL(redirectUri || 'http://127.0.0.1:4173/api/integrations/gmail/callback');
		url.searchParams.set('code', 'mock-code');
		url.searchParams.set('state', state);
		return url.toString();
	}

	const { clientId, redirectUri } = requireConfig();
	const params = new URLSearchParams({
		client_id: clientId,
		redirect_uri: redirectUri,
		response_type: 'code',
		scope: GMAIL_SCOPES.join(' '),
		access_type: 'offline',
		prompt: 'consent',
		include_granted_scopes: 'true',
		state
	});
	return `${AUTH_URL}?${params.toString()}`;
}

export async function exchangeGmailCode(code: string): Promise<GmailTokens> {
	if (isGmailMock()) {
		return {
			accessToken: `mock-access-${randomToken(8)}`,
			refreshToken: 'mock-refresh-token',
			expiresIn: 3600,
			scope: GMAIL_SCOPES.join(' ')
		};
	}

	const { clientId, clientSecret, redirectUri } = requireConfig();
	const response = await fetch(TOKEN_URL, {
		method: 'POST',
		headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
		body: new URLSearchParams({
			code,
			client_id: clientId,
			client_secret: clientSecret,
			redirect_uri: redirectUri,
			grant_type: 'authorization_code'
		})
	});

	if (!response.ok) {
		throw new Error(`Gmail token exchange failed (${response.status})`);
	}

	const data = (await response.json()) as {
		access_token: string;
		refresh_token?: string;
		expires_in: number;
		scope?: string;
	};

	return {
		accessToken: data.access_token,
		refreshToken: data.refresh_token ?? null,
		expiresIn: data.expires_in,
		scope: data.scope ?? null
	};
}

async function refreshAccessToken(refreshToken: string): Promise<string> {
	if (isGmailMock()) return `mock-access-${randomToken(8)}`;

	const { clientId, clientSecret } = requireConfig();
	const response = await fetch(TOKEN_URL, {
		method: 'POST',
		headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
		body: new URLSearchParams({
			refresh_token: refreshToken,
			client_id: clientId,
			client_secret: clientSecret,
			grant_type: 'refresh_token'
		})
	});

	if (!response.ok) {
		throw new Error(`Gmail token refresh failed (${response.status})`);
	}

	const data = (await response.json()) as { access_token: string };
	return data.access_token;
}

export async function fetchGmailProfile(accessToken: string): Promise<{ email: string | null }> {
	if (isGmailMock()) return { email: 'mock.candidate@gmail.com' };

	const response = await fetch(USERINFO_URL, {
		headers: { Authorization: `Bearer ${accessToken}` }
	});
	if (!response.ok) return { email: null };
	const data = (await response.json()) as { email?: string };
	return { email: data.email ?? null };
}

export type GmailDraftInput = {
	refreshToken: string;
	to: string;
	subject: string;
	body: string;
	attachments: KitAttachment[];
};

export async function createGmailDraft(input: GmailDraftInput) {
	if (isGmailMock()) {
		return {
			draftId: `mock-draft-${randomToken(8)}`,
			messageId: `mock-message-${randomToken(8)}`,
			mock: true
		};
	}

	const accessToken = await refreshAccessToken(input.refreshToken);
	const mime = buildMimeMessage({
		to: input.to,
		subject: input.subject,
		body: input.body,
		attachments: input.attachments
	});

	const response = await fetch(`${GMAIL_API}/drafts`, {
		method: 'POST',
		headers: {
			Authorization: `Bearer ${accessToken}`,
			'Content-Type': 'application/json'
		},
		body: JSON.stringify({ message: { raw: base64Url(mime) } })
	});

	if (!response.ok) {
		throw new Error(`Gmail draft creation failed (${response.status})`);
	}

	const data = (await response.json()) as {
		id: string;
		message?: { id?: string };
	};

	return {
		draftId: data.id,
		messageId: data.message?.id ?? null,
		mock: false
	};
}

export function gmailDraftLink(): string {
	return 'https://mail.google.com/mail/u/0/#drafts';
}
