import { z } from 'zod';
import { generateText } from './gemini';

export type ParsedRecipient = {
	email: string;
	field: string | null;
};

export type ApplicationInstructions = {
	recipients: ParsedRecipient[];
	selectedEmail: string | null;
	selectedField: string | null;
	subject: string | null;
	subjectTemplate: string | null;
	requiredDocuments: string[];
	combineAttachments: boolean;
	combinedFilename: string | null;
	oneFieldOnly: boolean;
	confidence: number;
	blockers: string[];
	notes: string | null;
	autoSendReady: boolean;
};

export type InstructionInput = {
	jobTitle: string;
	company: string | null;
	description: string;
	applyInstructions: string;
	candidate: {
		name: string;
		headline: string | null;
		targetFamilies: string[];
		resumeText: string;
	};
};

const EMAIL_PATTERN = /[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/gi;
const GENERAL_MAILBOXES = new Set([
	'jobs',
	'careers',
	'hr',
	'recruitment',
	'recruiting',
	'applications',
	'apply',
	'info',
	'admin',
	'office'
]);

const FAMILY_SYNONYMS: Record<string, string[]> = {
	software: [
		'software',
		'developer',
		'engineering',
		'technology',
		'programming',
		'computer',
		'systems'
	],
	data: ['data', 'analytics', 'analysis', 'ai', 'machine', 'science', 'statistics'],
	finance: ['finance', 'accounting', 'audit', 'banking', 'risk'],
	marketing: ['marketing', 'sales', 'commercial', 'brand', 'communications'],
	operations: ['operations', 'logistics', 'supply', 'procurement'],
	design: ['design', 'creative', 'product']
};

const DOC_ALIASES: Record<string, string> = {
	'cover letter': 'cover_letter',
	'covering letter': 'cover_letter',
	cv: 'cv',
	resume: 'cv',
	'curriculum vitae': 'cv',
	'national id': 'national_id',
	'national identification': 'national_id',
	'national identity': 'national_id',
	'national id copy': 'national_id',
	passport: 'national_id',
	certificate: 'certificate',
	certificates: 'certificate',
	transcript: 'transcript',
	transcripts: 'transcript',
	'academic transcript': 'transcript',
	'academic transcripts': 'transcript'
};

const DOC_LABELS: Record<string, string> = {
	cover_letter: 'cover letter',
	cv: 'CV',
	national_id: 'National ID',
	certificate: 'certificate',
	transcript: 'transcript'
};

const llmSchema = z.object({
	recipients: z
		.array(
			z.object({
				email: z.string().email(),
				field: z.string().max(200).nullish()
			})
		)
		.max(30)
		.default([]),
	recommended_email: z.string().email().nullish(),
	recommended_field: z.string().max(200).nullish(),
	required_documents: z.array(z.string().max(60)).max(10).default([]),
	combine_attachments: z.boolean().default(false),
	combined_filename: z.string().max(200).nullish(),
	subject: z.string().max(300).nullish(),
	one_field_only: z.boolean().default(false),
	confidence: z.number().min(0).max(1).default(0),
	notes: z.string().max(1000).nullish()
});

type LlmInstructions = z.infer<typeof llmSchema>;

function tokens(value: string): string[] {
	return value.toLowerCase().match(/[a-z0-9]+/g) ?? [];
}

function uniqueEmails(text: string): string[] {
	const found = new Set<string>();
	for (const match of text.matchAll(EMAIL_PATTERN)) {
		found.add(match[0].toLowerCase());
	}
	return [...found];
}

function fieldForEmail(text: string, email: string): string | null {
	const escaped = email.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
	for (const match of text.matchAll(new RegExp(escaped, 'gi'))) {
		const index = match.index ?? 0;
		const before = text.slice(Math.max(0, index - 1600), index);
		const lines = before
			.split(/\r?\n/)
			.map((line) => line.trim())
			.filter(Boolean)
			.reverse();
		for (const line of lines.slice(0, 14)) {
			const numbered = line.match(/^\d+[.)]\s+(.{2,120})$/);
			if (numbered) return numbered[1].trim();
			const labeled = line.match(/^(?:department|field|position|role)\s*[:\-]\s*(.{2,120})$/i);
			if (labeled) return labeled[1].trim();
		}
	}
	return null;
}

function deterministicRecipients(text: string): ParsedRecipient[] {
	return uniqueEmails(text).map((email) => ({
		email,
		field: fieldForEmail(text, email)
	}));
}

function mergeRecipients(
	primary: ParsedRecipient[],
	fallback: ParsedRecipient[]
): ParsedRecipient[] {
	const merged = new Map<string, ParsedRecipient>();
	for (const recipient of [...primary, ...fallback]) {
		const email = recipient.email.toLowerCase();
		const existing = merged.get(email);
		if (!existing) {
			merged.set(email, { email, field: recipient.field ?? null });
		} else if (!existing.field && recipient.field) {
			existing.field = recipient.field;
		}
	}
	return [...merged.values()];
}

function normalizeDocument(value: string): string | null {
	const key = value
		.trim()
		.toLowerCase()
		.replace(/[_-]+/g, ' ')
		.replace(/\s+/g, ' ');
	return DOC_ALIASES[key] ?? null;
}

function detectDocuments(text: string): string[] {
	const found = new Set<string>();
	if (/\bcover\s+letter\b/i.test(text)) found.add('cover_letter');
	if (/\b(cv|curriculum vitae|resume)\b/i.test(text)) found.add('cv');
	if (/\bnational\s+(id|identification|identity)\b|\bpassport\b/i.test(text)) {
		found.add('national_id');
	}
	if (/\bcertificat(e|es)\b/i.test(text)) found.add('certificate');
	if (/\btranscript(s)?\b/i.test(text)) found.add('transcript');
	if (found.size === 0) {
		found.add('cover_letter');
		found.add('cv');
	}
	return [...found];
}

function normalizeDocuments(values: string[], text: string): string[] {
	const found = new Set<string>();
	for (const value of values) {
		const normalized = normalizeDocument(value);
		if (normalized) found.add(normalized);
	}
	if (found.size === 0) {
		for (const value of detectDocuments(text)) found.add(value);
	}
	return [...found];
}

function cleanTemplate(value: string | null | undefined): string | null {
	if (!value) return null;
	const cleaned = value
		.replace(/^["'“”]+|["'“”]+$/g, '')
		.replace(/\s+/g, ' ')
		.trim()
		.slice(0, 300);
	return cleaned || null;
}

function detectSubject(text: string): string | null {
	const lines = text
		.split(/\r?\n/)
		.map((line) => line.trim())
		.filter(Boolean);
	const index = lines.findIndex((line) => /subject(?:\s+line)?/i.test(line));
	if (index === -1) return null;
	const sameLine = lines[index]
		.replace(/^.*?subject(?:\s+line)?\s*[:\-–]\s*/i, '')
		.trim();
	if (sameLine) return cleanTemplate(sameLine);
	return cleanTemplate(lines[index + 1]);
}

function detectCombine(text: string): boolean {
	return /\b(single|one)\s+(pdf|file|document)\b|\bcombine\b|\bmerged?\b/i.test(text);
}

function detectOneField(text: string): boolean {
	return /\bone\s+field\s+only\b|\bonly\s+one\s+field\b|\bcandidates?\s+may\s+apply\s+for\s+one\b/i.test(
		text
	);
}

function fillSubject(template: string | null, field: string | null): string | null {
	if (!template) return null;
	if (!field) return template;
	return template.replace(/\[field\]|\{field\}/gi, field).replace(/\s{2,}/g, ' ').trim();
}

function extractJson(value: string): unknown {
	const text = value.trim();
	const start = text.indexOf('{');
	const end = text.lastIndexOf('}');
	if (start === -1 || end <= start) return null;
	try {
		return JSON.parse(text.slice(start, end + 1));
	} catch {
		return null;
	}
}

function bestRecipient(
	recipients: ParsedRecipient[],
	input: InstructionInput
): ParsedRecipient | null {
	if (recipients.length === 1) return recipients[0];
	const families = input.candidate.targetFamilies.map((family) => family.toLowerCase());
	const context = new Set(
		tokens(`${input.candidate.headline ?? ''} ${input.jobTitle}`).filter(
			(token) => token.length >= 4
		)
	);

	let best: ParsedRecipient | null = null;
	let bestScore = 0;
	let tied = false;

	for (const recipient of recipients) {
		const labelTokens = new Set(
			tokens(`${recipient.field ?? ''} ${recipient.email.split('@')[0]}`)
		);
		let score = 0;
		for (const family of families) {
			if (labelTokens.has(family)) score += 3;
			for (const synonym of FAMILY_SYNONYMS[family] ?? []) {
				if (labelTokens.has(synonym)) score += 1;
			}
		}
		for (const token of context) {
			if (labelTokens.has(token)) score += 1;
		}
		if (score > bestScore) {
			best = recipient;
			bestScore = score;
			tied = false;
		} else if (score === bestScore && score > 0) {
			tied = true;
		}
	}

	if (bestScore > 0 && !tied) return best;
	const general = recipients.filter((recipient) =>
		GENERAL_MAILBOXES.has(recipient.email.split('@')[0])
	);
	return general.length === 1 ? general[0] : null;
}

async function parseWithModel(input: InstructionInput): Promise<LlmInstructions | null> {
	const prompt = `You extract job application instructions. Return JSON only, no markdown fences.

Candidate:
Headline: ${input.candidate.headline ?? 'Not provided'}
Target fields: ${input.candidate.targetFamilies.join(', ') || 'Not provided'}
Resume:
${input.candidate.resumeText.slice(0, 4000)}

Job title: ${input.jobTitle}
Company: ${input.company ?? 'Not provided'}

Job description:
${input.description.slice(0, 8000)}

Application instructions:
${input.applyInstructions.slice(0, 3000)}

Return this exact JSON shape:
{
  "recipients": [{"email": "...", "field": "..."}],
  "recommended_email": "..." or null,
  "recommended_field": "..." or null,
  "required_documents": ["cover_letter", "cv"],
  "combine_attachments": false,
  "combined_filename": "..." or null,
  "subject": "..." or null,
  "one_field_only": false,
  "confidence": 0.0,
  "notes": "..."
}

Rules:
- List every distinct application email once, with the field or role it belongs to when the post lists multiple fields.
- Choose the one recipient that best fits the candidate's actual qualifications and target fields. If the post requires one field only and two fields are equally plausible, return null for recommended_email and confidence below 0.5.
- required_documents may only contain: cover_letter, cv, national_id, certificate, transcript. Only include documents the applicant must attach or submit with this application; ignore general eligibility or qualification documents. If the post does not list documents, use ["cover_letter", "cv"].
- combine_attachments is true only when the post asks for one PDF, file or document.
- subject is the exact subject line requested, preserving placeholders such as [Field]. Return null if none.
- confidence measures how clearly the posting states its application instructions, not whether the candidate is a strong fit; the matcher already selected this role.
- Do not invent emails, documents or requirements.`;

	const text = await generateText(prompt, 0.1);
	if (!text) return null;
	const parsed = llmSchema.safeParse(extractJson(text));
	return parsed.success ? parsed.data : null;
}

export async function parseApplicationInstructions(
	input: InstructionInput
): Promise<ApplicationInstructions> {
	const combined = `${input.description}\n${input.applyInstructions}`.trim();
	const fallbackRecipients = deterministicRecipients(combined);
	const model = await parseWithModel(input);
	const modelRecipients = (model?.recipients ?? []).map((recipient) => ({
		email: recipient.email.toLowerCase(),
		field: recipient.field ?? null
	}));
	const recipients = mergeRecipients(modelRecipients, fallbackRecipients);
	const requiredDocuments = normalizeDocuments(model?.required_documents ?? [], combined);
	const subjectTemplate = cleanTemplate(model ? model.subject : detectSubject(combined));
	const combineAttachments = model ? model.combine_attachments : detectCombine(combined);
	const oneFieldOnly = model ? model.one_field_only : detectOneField(combined);
	const blockers: string[] = [];

	let selectedEmail: string | null = null;
	let confidence = 0;
	let selectedByModel = false;

	const modelEmail = model?.recommended_email?.toLowerCase() ?? null;
	if (modelEmail && recipients.some((recipient) => recipient.email === modelEmail)) {
		selectedEmail = modelEmail;
		confidence = model?.confidence ?? 0;
		selectedByModel = true;
	}
	if (!selectedEmail) {
		const best = bestRecipient(recipients, input);
		if (best) {
			selectedEmail = best.email;
			confidence = Math.max(confidence, recipients.length === 1 ? 0.8 : 0.7);
		}
	}
	if (recipients.length === 1) {
		confidence = Math.max(confidence, 0.8);
	}

	const selected = recipients.find((recipient) => recipient.email === selectedEmail) ?? null;
	const selectedField = model?.recommended_field?.trim() || selected?.field || null;

	if (recipients.length === 0) {
		blockers.push('No application email found');
	} else if (!selectedEmail) {
		blockers.push('Multiple application addresses; no confident field match');
	}
	if (selectedByModel && recipients.length > 1 && confidence < 0.5) {
		blockers.push('Instruction parsing confidence is low');
	}
	if (oneFieldOnly && !selectedField) {
		blockers.push('Posting allows one field only and no field was selected');
	}
	if (subjectTemplate && /\[field\]|\{field\}/i.test(subjectTemplate) && !selectedField) {
		blockers.push('Subject line needs a field but none was selected');
	}

	const subject = fillSubject(subjectTemplate, selectedField);
	const autoSendReady =
		Boolean(selectedEmail) && blockers.length === 0 && confidence >= 0.5;

	return {
		recipients,
		selectedEmail,
		selectedField,
		subject,
		subjectTemplate,
		requiredDocuments,
		combineAttachments,
		combinedFilename: cleanTemplate(model?.combined_filename),
		oneFieldOnly,
		confidence: Math.round(confidence * 100) / 100,
		blockers,
		notes: model?.notes ?? null,
		autoSendReady
	};
}

export function documentLabel(document: string): string {
	return DOC_LABELS[document] ?? document;
}
