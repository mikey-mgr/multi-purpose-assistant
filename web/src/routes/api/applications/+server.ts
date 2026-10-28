import { json } from '@sveltejs/kit';
import { z } from 'zod';
import type { RequestHandler } from './$types';
import {
	MAX_ATTACHMENT_BYTES,
	decodedBase64Size
} from '../../../lib/server/application-kit';
import { getDb } from '../../../lib/server/db';
import { applicationKits } from '../../../lib/server/db/schema';
import { rateLimit, rateLimitKey, tooManyRequests } from '../../../lib/server/rate-limit';

const attachmentInput = z
	.object({
		name: z
			.string()
			.min(1)
			.max(120)
			.regex(/^[A-Za-z0-9._ -]+$/),
		mime: z.string().min(3).max(100).regex(/^[a-z0-9.+-]+\/[a-z0-9.+-]+$/i),
		contentBase64: z
			.string()
			.min(4)
			.max(12_000_000)
			.regex(/^[A-Za-z0-9+/=\s]+$/)
	})
	.strict();

const kitInput = z
	.object({
		jobId: z.string().max(80).optional(),
		jobTitle: z.string().trim().max(160).optional(),
		company: z.string().trim().max(160).optional(),
		recipient: z.string().email().max(320),
		subject: z.string().trim().min(1).max(200),
		body: z.string().min(1).max(30_000),
		attachments: z.array(attachmentInput).max(5).default([])
	})
	.strict();

export const POST: RequestHandler = async (event) => {
	if (!event.locals.user) {
		return json({ error: 'Unauthorized' }, { status: 401 });
	}

	const limit = await rateLimit(rateLimitKey(event, 'applications:create'), 10, 3600);
	if (!limit.allowed) return tooManyRequests(limit);

	let body: unknown;
	try {
		body = await event.request.json();
	} catch {
		return json({ error: 'Invalid JSON body' }, { status: 400 });
	}

	const parsed = kitInput.safeParse(body);
	if (!parsed.success) {
		return json({ error: 'Invalid application kit', issues: parsed.error.flatten() }, { status: 400 });
	}

	let totalBytes = 0;
	for (const attachment of parsed.data.attachments) {
		const size = decodedBase64Size(attachment.contentBase64);
		if (size <= 0) {
			return json({ error: `Attachment ${attachment.name} is empty` }, { status: 400 });
		}
		totalBytes += size;
	}

	if (totalBytes > MAX_ATTACHMENT_BYTES) {
		return json({ error: 'Attachments exceed the 8 MB limit' }, { status: 413 });
	}

	const db = await getDb();
	const id = crypto.randomUUID();
	const createdAt = new Date();
	await db.insert(applicationKits).values({
		id,
		userId: event.locals.user.id,
		jobId: parsed.data.jobId,
		jobTitle: parsed.data.jobTitle,
		company: parsed.data.company,
		recipient: parsed.data.recipient,
		subject: parsed.data.subject,
		body: parsed.data.body,
		attachments: parsed.data.attachments,
		createdAt
	});

	return json({
		id,
		createdAt,
		attachments: parsed.data.attachments.map((attachment) => ({
			name: attachment.name,
			mime: attachment.mime,
			bytes: decodedBase64Size(attachment.contentBase64)
		}))
	});
};
