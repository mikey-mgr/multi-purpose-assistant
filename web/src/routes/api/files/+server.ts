import { json } from '@sveltejs/kit';
import { desc, eq } from 'drizzle-orm';
import type { RequestHandler } from './$types';
import { getDb } from '../../../lib/server/db';
import { profiles, userFiles } from '../../../lib/server/db/schema';
import { deleteFile, extractResumeText, putFile } from '../../../lib/server/file-storage';
import { triggerMatchingForUser } from '../../../lib/server/matching';
import { rateLimit, rateLimitKey, tooManyRequests } from '../../../lib/server/rate-limit';
import { buildAutofillSuggestions } from '../../../lib/server/resume/autofill';
import { extractResumeProfile } from '../../../lib/server/resume/extract';

const MAX_BYTES = 15 * 1024 * 1024;
const ALLOWED_PURPOSES = new Set(['resume', 'national_id', 'document']);
const ALLOWED_TYPES = new Set([
	'application/pdf',
	'application/msword',
	'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
	'image/jpeg',
	'image/png',
	'image/webp',
	'text/plain'
]);

function safeFilename(name: string): string {
	return name
		.replace(/[^a-zA-Z0-9._-]/g, '_')
		.replace(/^\.+/, '')
		.slice(0, 120) || 'file';
}

export const GET: RequestHandler = async (event) => {
	if (!event.locals.user) {
		return json({ error: 'Unauthorized' }, { status: 401 });
	}

	const limit = await rateLimit(rateLimitKey(event, 'files:list'), 120, 60);
	if (!limit.allowed) return tooManyRequests(limit);

	const db = await getDb();
	const rows = await db
		.select()
		.from(userFiles)
		.where(eq(userFiles.userId, event.locals.user.id))
		.orderBy(desc(userFiles.createdAt))
		.limit(100);

	return json(
		{
			files: rows.map((row) => ({
				id: row.id,
				filename: row.filename,
				contentType: row.contentType,
				purpose: row.purpose,
				size: row.size,
				createdAt: row.createdAt
			}))
		},
		{ headers: { 'Cache-Control': 'no-store' } }
	);
};

export const POST: RequestHandler = async (event) => {
	if (!event.locals.user) {
		return json({ error: 'Unauthorized' }, { status: 401 });
	}

	const limit = await rateLimit(rateLimitKey(event, 'files:upload'), 30, 3600);
	if (!limit.allowed) return tooManyRequests(limit);

	let form: FormData;
	try {
		form = await event.request.formData();
	} catch {
		return json({ error: 'Invalid upload' }, { status: 400 });
	}

	const file = form.get('file');
	if (!(file instanceof File) || file.size === 0) {
		return json({ error: 'Choose a file to upload' }, { status: 400 });
	}
	if (file.size > MAX_BYTES) {
		return json({ error: 'File is larger than 15 MB' }, { status: 413 });
	}
	if (!ALLOWED_TYPES.has(file.type)) {
		return json({ error: 'Unsupported file type' }, { status: 415 });
	}

	const requestedPurpose = String(form.get('purpose') ?? 'document');
	const purpose = ALLOWED_PURPOSES.has(requestedPurpose) ? requestedPurpose : 'document';
	const filename = safeFilename(file.name);
	const key = `users/${event.locals.user.id}/${crypto.randomUUID()}-${filename}`;
	if (!(await putFile(key, file))) {
		return json({ error: 'File storage is not configured' }, { status: 503 });
	}

	const db = await getDb();
	const id = crypto.randomUUID();
	try {
		await db.insert(userFiles).values({
			id,
			userId: event.locals.user.id,
			filename,
			contentType: file.type,
			purpose,
			size: file.size,
			r2Key: key
		});
		let resumeUpdated = false;
		let suggestions = null;
		let resumeText: string | null = null;
		let extractedReferences: unknown[] = [];
		if (purpose === 'resume') {
			resumeText = await extractResumeText(file);
			const text = resumeText;
			if (text) {
				const structured = await extractResumeProfile({
					name: event.locals.user.name,
					email: event.locals.user.email,
					resumeText: text
				});
				const updatedAt = new Date();
				const existing = await db
					.select({ references: profiles.references })
					.from(profiles)
					.where(eq(profiles.userId, event.locals.user.id))
					.limit(1);
				const savedReferences = existing[0]?.references ?? [];

				// Only adopt referees from the CV when the user has not saved their own.
				const extracted = (structured?.references ?? []).map((referee) => ({
					id: crypto.randomUUID(),
					name: referee.name,
					role: referee.role ?? null,
					organisation: referee.organisation ?? null,
					email: referee.email ?? null,
					phone: referee.phone ?? null
				}));
				const referencesToSave = savedReferences.length ? savedReferences : extracted;
				extractedReferences = referencesToSave;

				const structuredFields = structured
					? {
							resumeData: structured,
							...(structured.user.phone_1 ? { phone: structured.user.phone_1 } : {}),
							...(structured.user.linkedin_url
								? { linkedinUrl: structured.user.linkedin_url }
								: {}),
							...(referencesToSave.length ? { references: referencesToSave } : {})
						}
					: {};
				await db
					.insert(profiles)
					.values({
						userId: event.locals.user.id,
						resumeText: text,
						updatedAt,
						...structuredFields
					})
					.onConflictDoUpdate({
						target: profiles.userId,
						set: { resumeText: text, updatedAt, ...structuredFields }
					});
				resumeUpdated = true;
				suggestions = structured ? buildAutofillSuggestions(structured) : null;
				await triggerMatchingForUser({ userId: event.locals.user.id });
			}
		}
		return json(
			{
				file: {
					id,
					filename,
					contentType: file.type,
					purpose,
					size: file.size,
					createdAt: new Date()
				},
				resumeUpdated,
				resumeText,
				suggestions,
				references: extractedReferences
			},
			{ status: 201 }
		);
	} catch {
		await deleteFile(key);
		return json({ error: 'Could not save the file' }, { status: 500 });
	}
};
