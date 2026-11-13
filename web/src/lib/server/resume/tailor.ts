import { z } from 'zod';
import { generateText } from '../gemini';
import { ATS_AND_COVER_PROMPT } from './ats-and-cover-prompt';
import type { ResumeProfile, TailoredApplication } from './types';

export type TailorJob = {
	title: string;
	company: string | null;
	description: string;
	location?: string | null;
	jobType?: string | null;
	applyInstructions?: string | null;
	documents?: Record<string, string>;
};

const schema = z.object({
	resume: z.object({
		summary: z.string().max(4000).optional(),
		experience_highlights: z
			.record(z.string(), z.array(z.string().max(1200)))
			.optional(),
		skills: z
			.array(
				z.object({
					label: z.string().max(120),
					details: z.string().max(1000)
				})
			)
			.max(8)
			.optional(),
		project_highlights: z
			.record(z.string(), z.array(z.string().max(1200)))
			.optional(),
		references: z.unknown().optional()
	}),
	cover_letter: z.string().max(8000).nullable().optional(),
	apply_details: z
		.object({
			action: z.enum(['email', 'external_link', 'unknown']).optional(),
			recipient: z.string().max(250).nullable().optional(),
			subject: z.string().max(400).nullable().optional(),
			body: z.string().max(5000).nullable().optional(),
			url: z.string().max(3000).nullable().optional(),
			required_docs: z.array(z.string().max(60)).max(12).optional(),
			proceed: z.enum(['apply_now', 'needs_docs', 'needs_info']).optional(),
			expiry_date: z.string().max(30).nullable().optional(),
			merged_pdf: z.boolean().optional()
		})
		.optional(),
	missing_resources: z.string().max(5000).nullable().optional()
});

function parseJson(value: string): unknown {
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

export async function tailorApplication(
	profile: ResumeProfile,
	job: TailorJob
): Promise<TailoredApplication | null> {
	const userProfile = JSON.stringify({
		...profile,
		documents: job.documents ?? profile.documents ?? {}
	});
	const jobDescription = JSON.stringify({
		title: job.title,
		company: job.company,
		description: job.description,
		location: job.location ?? null,
		job_type: job.jobType ?? null,
		apply_instructions: job.applyInstructions ?? null
	});
	const prompt = ATS_AND_COVER_PROMPT.replaceAll('{{user_profile}}', userProfile).replaceAll(
		'{{job_description}}',
		jobDescription
	);
	const text = await generateText(prompt, 0.7, 8000);
	if (!text) return null;
	const parsed = schema.safeParse(parseJson(text));
	if (!parsed.success) return null;

	return {
		resume: {
			summary: parsed.data.resume.summary,
			skills: parsed.data.resume.skills,
			experience_highlights: parsed.data.resume.experience_highlights,
			project_highlights: parsed.data.resume.project_highlights
		},
		coverLetter: parsed.data.cover_letter?.trim() || null,
		applyDetails: parsed.data.apply_details ?? {},
		missingResources: parsed.data.missing_resources ?? null
	};
}
