import { eq } from 'drizzle-orm';
import { generateText } from '../gemini';
import { getDb } from '../db';
import { documents, profiles } from '../db/schema';
import { getFile, putFile } from '../file-storage';
import { CV_TEMPLATES, type CvTemplate } from '../../cv-templates';
import { base64ToBytes } from './kit';
import { buildCvData } from './build-cv';
import { renderApplication } from './render-service';
import type { ResumeProfile } from './types';

export type BaseCvResult = {
	documentId: string;
	theme: CvTemplate;
	pages: number;
	polished: boolean;
};

const THEMES = new Set<string>(CV_TEMPLATES.map((template) => template.value));

export function isCvTemplate(value: string): value is CvTemplate {
	return THEMES.has(value);
}

/**
 * Rewrite the profile summary and bullets so they read as one consistent CV.
 * Facts, dates, employers and metrics are preserved; only wording changes.
 */
async function polishProfile(profile: ResumeProfile): Promise<ResumeProfile | null> {
	const payload = {
		summary: profile.resume.professional_summary,
		experiences: profile.experiences.map((experience) => ({
			company: experience.company_name,
			title: experience.job_title,
			start: experience.start_date,
			end: experience.end_date,
			bullets: experience.bullet_points
		})),
		projects: profile.projects.map((project) => ({
			name: project.project_name,
			bullets: project.bullet_points
		}))
	};

	const prompt = `Rewrite this CV content so it reads as one polished, professional CV.

Return ONLY JSON, no markdown fences:
{
  "summary": "2-3 sentence professional summary",
  "experiences": [{ "company": "...", "bullets": ["..."] }],
  "projects": [{ "name": "...", "bullets": ["..."] }]
}

Rules:
- Keep every employer, job title, project, date and number exactly as given. Do not invent anything.
- Start each bullet with a strong past-tense verb; keep existing metrics, never add new ones.
- One line per bullet, no filler phrases, no first-person "I".
- Keep the same number of bullets per role unless two are clearly duplicates.
- Do not use em dashes or en dashes; use a plain hyphen or a comma instead.

CV content:
${JSON.stringify(payload).slice(0, 15000)}`;

	const text = await generateText(prompt, 0.3, 4000);
	if (!text) return null;

	const start = text.indexOf('{');
	const end = text.lastIndexOf('}');
	if (start === -1 || end <= start) return null;

	let parsed: {
		summary?: unknown;
		experiences?: unknown;
		projects?: unknown;
	};
	try {
		parsed = JSON.parse(text.slice(start, end + 1));
	} catch {
		return null;
	}

	const polishedExperience = new Map<string, string[]>();
	if (Array.isArray(parsed.experiences)) {
		for (const entry of parsed.experiences) {
			if (!entry || typeof entry !== 'object') continue;
			const record = entry as { company?: unknown; bullets?: unknown };
			if (typeof record.company !== 'string' || !Array.isArray(record.bullets)) continue;
			const bullets = record.bullets
				.filter((bullet): bullet is string => typeof bullet === 'string')
				.map((bullet) => bullet.trim())
				.filter(Boolean)
				.slice(0, 20);
			if (bullets.length) polishedExperience.set(record.company, bullets);
		}
	}

	const polishedProjects = new Map<string, string[]>();
	if (Array.isArray(parsed.projects)) {
		for (const entry of parsed.projects) {
			if (!entry || typeof entry !== 'object') continue;
			const record = entry as { name?: unknown; bullets?: unknown };
			if (typeof record.name !== 'string' || !Array.isArray(record.bullets)) continue;
			const bullets = record.bullets
				.filter((bullet): bullet is string => typeof bullet === 'string')
				.map((bullet) => bullet.trim())
				.filter(Boolean)
				.slice(0, 20);
			if (bullets.length) polishedProjects.set(record.name, bullets);
		}
	}

	return {
		...profile,
		resume: {
			...profile.resume,
			professional_summary:
				typeof parsed.summary === 'string' && parsed.summary.trim()
					? parsed.summary.trim().slice(0, 4000)
					: profile.resume.professional_summary
		},
		experiences: profile.experiences.map((experience) => ({
			...experience,
			bullet_points: polishedExperience.get(experience.company_name) ?? experience.bullet_points
		})),
		projects: profile.projects.map((project) => ({
			...project,
			bullet_points: polishedProjects.get(project.project_name) ?? project.bullet_points
		}))
	};
}

/**
 * Render a general-purpose CV straight from the user's stored profile, with no
 * job attached. Lets someone polish and download a CV before any match exists.
 */
export async function generateBaseCv(input: {
	userId: string;
	theme: CvTemplate;
	polish: boolean;
}): Promise<{ result: BaseCvResult | null; error?: string }> {
	const db = await getDb();
	const rows = await db
		.select()
		.from(profiles)
		.where(eq(profiles.userId, input.userId))
		.limit(1);

	const profile = rows[0];
	if (!profile) return { result: null, error: 'Set up your profile first' };
	if (!profile.resumeData) {
		return {
			result: null,
			error: 'Upload or paste your CV first so we have your history to work from'
		};
	}

	const source = profile.resumeData as ResumeProfile;
	const finalProfile = input.polish ? ((await polishProfile(source)) ?? source) : source;
	const polished = input.polish && finalProfile !== source;

	const cv = buildCvData(finalProfile, {}, {
		references: profile.references ?? [],
		referencesEnabled: profile.referencesEnabled ?? false
	});

	const outcome = await renderApplication({
		cv,
		theme: input.theme,
		coverLetter: null,
		attachments: [],
		merge: false
	});
	if (!outcome.result) {
		return { result: null, error: outcome.error ?? 'Renderer unavailable' };
	}

	const name = `${finalProfile.user.first_name} ${finalProfile.user.last_name}`.trim() || 'CV';
	const filename = `${name.replace(/[^a-zA-Z0-9 ]/g, '')} CV.pdf`;
	const key = `users/${input.userId}/base-cv/${crypto.randomUUID()}-${filename}`;
	const stored = await putFile(
		key,
		new File([base64ToBytes(outcome.result.cvPdf) as BlobPart], filename, {
			type: 'application/pdf'
		})
	);
	if (!stored) return { result: null, error: 'Could not store the CV' };

	const documentId = crypto.randomUUID();
	await db.insert(documents).values({
		id: documentId,
		userId: input.userId,
		jobId: null,
		documentType: 'resume',
		content: JSON.stringify(cv),
		rendercvYaml: JSON.stringify({ cv, design: { theme: input.theme } }),
		pdfPath: key,
		promptName: polished ? 'base_cv_polished' : 'base_cv',
		model: 'rendercv'
	});

	return {
		result: {
			documentId,
			theme: input.theme,
			pages: outcome.result.cvPages,
			polished
		}
	};
}

/** Fetch a stored base CV PDF for download. */
export async function getBaseCvFile(input: {
	userId: string;
	documentId: string;
}): Promise<{ bytes: ArrayBuffer; filename: string } | null> {
	const db = await getDb();
	const rows = await db
		.select()
		.from(documents)
		.where(eq(documents.id, input.documentId))
		.limit(1);

	const document = rows[0];
	if (!document || document.userId !== input.userId || !document.pdfPath) return null;

	const response = await getFile(document.pdfPath);
	if (!response) return null;

	return {
		bytes: await response.arrayBuffer(),
		filename: document.pdfPath.split('/').pop() ?? 'CV.pdf'
	};
}
