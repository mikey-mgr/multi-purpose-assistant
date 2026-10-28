import { randomToken } from './crypto';
import type { KitAttachment } from './db/schema';

export type MimeMessageInput = {
	to: string;
	subject: string;
	body: string;
	attachments: KitAttachment[];
	date?: Date;
};

function sanitizeHeader(value: string, field: string): string {
	if (/[\r\n]/.test(value)) {
		throw new Error(`${field} must not contain line breaks`);
	}
	return value.trim();
}

function base64Lines(value: string): string {
	return value.replace(/.{1,76}/g, (line) => `${line}\r\n`).trimEnd();
}

function utf8ToBase64(value: string): string {
	const bytes = new TextEncoder().encode(value);
	let binary = '';
	for (const byte of bytes) binary += String.fromCharCode(byte);
	return btoa(binary);
}

function encodeSubject(subject: string): string {
	const clean = sanitizeHeader(subject, 'Subject');
	return `=?UTF-8?B?${utf8ToBase64(clean)}?=`;
}

function bodyBase64(body: string): string {
	return base64Lines(utf8ToBase64(body));
}

export function buildMimeMessage(input: MimeMessageInput): string {
	const to = sanitizeHeader(input.to, 'To');
	const subject = encodeSubject(input.subject);
	const boundary = `----mukana_${randomToken(12)}`;
	const date = (input.date ?? new Date()).toUTCString();

	const lines: string[] = [
		`To: ${to}`,
		`Subject: ${subject}`,
		`Date: ${date}`,
		'MIME-Version: 1.0',
		`Content-Type: multipart/mixed; boundary="${boundary}"`,
		'',
		`--${boundary}`,
		'Content-Type: text/plain; charset=UTF-8',
		'Content-Transfer-Encoding: base64',
		'',
		bodyBase64(input.body),
		''
	];

	for (const attachment of input.attachments) {
		const name = sanitizeHeader(attachment.name, 'Attachment name').replace(/["\\]/g, '');
		const mime = sanitizeHeader(attachment.mime, 'Attachment type');
		lines.push(
			`--${boundary}`,
			`Content-Type: ${mime}; name="${name}"`,
			'Content-Transfer-Encoding: base64',
			`Content-Disposition: attachment; filename="${name}"`,
			'',
			base64Lines(attachment.contentBase64),
			''
		);
	}

	lines.push(`--${boundary}--`, '');
	return lines.join('\r\n');
}

export function buildEml(input: MimeMessageInput): string {
	return buildMimeMessage(input);
}

export function composeLinks(to: string, subject: string, body: string) {
	const params = new URLSearchParams({ to, su: subject, body });
	const shortBody = body.length > 6000 ? `${body.slice(0, 6000)}\n\n[Full letter attached]` : body;
	const shortParams = new URLSearchParams({ to, su: subject, body: shortBody });

	return {
		gmail: `https://mail.google.com/mail/?view=cm&fs=1&${shortParams.toString()}`,
		outlook: `https://outlook.live.com/mail/0/deeplink/compose?${shortParams.toString()}`,
		yahoo: `https://compose.mail.yahoo.com/?${shortParams.toString()}`,
		mailto: `mailto:${encodeURIComponent(to)}?${new URLSearchParams({
			subject,
			body: shortBody
		}).toString()}`,
		plain: params.toString()
	};
}
