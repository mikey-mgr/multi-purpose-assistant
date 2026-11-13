import { generateText, generateTextWithImage } from './gemini';

export type ParsedJob = {
	title: string;
	company: string | null;
	location: string | null;
	job_type: string | null;
	compensation: string | null;
	date_posted: string | null;
	expires: string | null;
	category: string | null;
	remote: string | null;
	apply_instructions: string | null;
	description: string | null;
};

const FIELDS = `{
  "is_job_posting": true,
  "title": "job title",
  "company": "employer name or null",
  "location": "location or null",
  "job_type": "Full-time | Part-time | Contract | Internship | null",
  "compensation": "salary if stated or null",
  "date_posted": "YYYY-MM-DD or null",
  "expires": "YYYY-MM-DD or null",
  "category": "short category or null",
  "remote": "Remote | On-site | Hybrid | null",
  "apply_instructions": "the exact application instructions, including any email address or URL and required documents, or null",
  "description": "the full job description, preserving all requirements and duties"
}`;

const RULES = `Rules:
- Set is_job_posting to false when the message is not a vacancy (a question, a greeting, or chatter).
- Copy facts from the posting. Do not invent a company, salary, deadline or email.
- If a field is absent, use null. Never write "N/A" or "not stated".
- apply_instructions must contain any email address or apply URL verbatim.`;

const TEXT_PROMPT = `Read this WhatsApp message containing a job posting.

Return ONLY a JSON object. No markdown fences, no commentary.

${FIELDS}

${RULES}

Message:
`;

const IMAGE_PROMPT = `This image is a job posting shared on WhatsApp.

Return ONLY a JSON object. No markdown fences, no commentary.

${FIELDS}

${RULES}

Return only the JSON object.`;

function extractJson(text: string | null): Record<string, unknown> | null {
	if (!text) return null;
	let cleaned = text.trim();
	if (cleaned.includes('```')) {
		cleaned = cleaned.replace(/^```[a-zA-Z]*\s*/, '').split('```')[0];
	}
	const start = cleaned.indexOf('{');
	const end = cleaned.lastIndexOf('}');
	if (start === -1 || end <= start) return null;
	try {
		const parsed = JSON.parse(cleaned.slice(start, end + 1));
		return parsed && typeof parsed === 'object' ? (parsed as Record<string, unknown>) : null;
	} catch {
		return null;
	}
}

const EMPTY_VALUES = new Set(['n/a', 'na', 'none', 'null', 'not stated', 'unknown']);

function clean(payload: Record<string, unknown> | null): ParsedJob | null {
	if (!payload || payload.is_job_posting === false) return null;
	const title = typeof payload.title === 'string' ? payload.title.trim().slice(0, 500) : '';
	if (!title) return null;

	const value = (key: string, max: number): string | null => {
		const raw = payload[key];
		if (typeof raw !== 'string') return null;
		const text = raw.trim();
		if (!text || EMPTY_VALUES.has(text.toLowerCase())) return null;
		return text.slice(0, max);
	};

	const date = (key: string): string | null => {
		const raw = payload[key];
		if (typeof raw !== 'string') return null;
		const text = raw.trim().slice(0, 10);
		return /^\d{4}-\d{2}-\d{2}$/.test(text) ? text : null;
	};

	return {
		title,
		company: value('company', 300),
		location: value('location', 300),
		job_type: value('job_type', 100),
		compensation: value('compensation', 200),
		date_posted: date('date_posted'),
		expires: date('expires'),
		category: value('category', 200),
		remote: value('remote', 100),
		apply_instructions: value('apply_instructions', 20_000),
		description: value('description', 100_000)
	};
}

/** Extract a job from WhatsApp text. Returns null when the message is not a vacancy. */
export async function parseTextJob(text: string): Promise<ParsedJob | null> {
	const content = await generateText(`${TEXT_PROMPT}${text.slice(0, 8000)}`, 0.1, 3000);
	return clean(extractJson(content));
}

/**
 * Decide whether a message is a request to resend already-generated documents.
 *
 * Kept as a cheap keyword check rather than a model call: this runs before job
 * parsing on every inbound message, and a mis-parse here would be confusing.
 *
 * The hard part is that a real job posting usually says "Send your CV to
 * jobs@company.co.zw". That is an instruction to the applicant, not a request to
 * us, so vacancy signals always win and only first-person requests qualify.
 */
export function detectDocumentRequest(text: string): { wantsCopy: boolean; reference: string | null } {
	const lower = text.toLowerCase().trim();
	const no = { wantsCopy: false, reference: null };

	// A posting: has vacancy wording, an application address, or a deadline.
	const looksLikePosting =
		/\b(vacancy|vacancies|position|positions|we are (hiring|looking)|now hiring|job title|responsibilities|requirements|qualifications|deadline|closing date|applications? (are|is) invited|ref no)\b/.test(
			lower
		) ||
		/[\w.+-]+@[\w-]+\.[\w.]+/.test(lower) ||
		/https?:\/\//.test(lower);
	if (looksLikePosting) return no;

	// Must ask *us* for documents, in the first person.
	const mentionsDoc =
		/\b(cv|resume|curriculum|cover letter|coverletter|documents?|pdf)\b/.test(lower);
	const asksMe =
		/\b(send|resend|share|forward|whatsapp|give)\b[^.!?]{0,30}\b(me|my|mine)\b/.test(lower) ||
		/^(please\s+)?(can|could)\s+you\s+(send|resend|share|forward|whatsapp)\b/.test(lower);
	if (!mentionsDoc || !asksMe) return no;

	// "send me my latest CV" means the newest kit; anything else names a job.
	if (/\b(latest|recent|last|newest)\b/.test(lower)) return { wantsCopy: true, reference: null };

	const generic =
		/^(please\s+)?(can you\s+)?(send|resend|share|forward|whatsapp)\b[\s\w]{0,12}\b(me|my)\b[\s\w]{0,12}\b(cv|resume|cover letter|documents?|pdf)\b\s*[?.!]*$/;
	if (generic.test(lower)) return { wantsCopy: true, reference: null };

	const reference = lower
		.replace(/\b(please|can you|could you|send|resend|share|forward|whatsapp|give)\b/g, ' ')
		.replace(/\b(me|my|mine|the|a|an)\b/g, ' ')
		.replace(/\b(cv|resume|curriculum vitae|cover letter|coverletter|documents?|pdf)\b/g, ' ')
		.replace(/\b(for|about|of|to|on)\b/g, ' ')
		.replace(/[^a-z0-9 ]/g, ' ')
		.replace(/\s+/g, ' ')
		.trim();

	return { wantsCopy: true, reference: reference.length >= 3 ? reference : null };
}

/** Extract a job from a WhatsApp image. Returns null when the image is not a vacancy. */
export async function parseImageJob(
	imageBase64: string,
	mimetype: string
): Promise<ParsedJob | null> {
	const content = await generateTextWithImage(IMAGE_PROMPT, imageBase64, mimetype);
	return clean(extractJson(content));
}
