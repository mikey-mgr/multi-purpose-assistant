import { z } from 'zod';
import { generateText } from '../gemini';
import type { ResumeProfile } from './types';

const profileSchema = z.object({
	user: z.object({
		first_name: z.string().max(120).optional(),
		last_name: z.string().max(120).optional(),
		email: z.string().max(250).optional(),
		phone_1: z.string().max(60).nullable().optional(),
		phone_2: z.string().max(60).nullable().optional(),
		linkedin_url: z.string().max(500).nullable().optional(),
		location_city: z.string().max(120).nullable().optional(),
		location_country: z.string().max(120).nullable().optional()
	}),
	resume: z.object({
		professional_summary: z.string().max(4000).nullable().optional(),
		additional_information: z.record(z.string(), z.unknown()).nullable().optional()
	}),
	experiences: z
		.array(
			z.object({
				company_name: z.string().max(250),
				job_title: z.string().max(250),
				location: z.string().max(250).nullable().optional(),
				start_date: z.string().max(30).nullable().optional(),
				end_date: z.string().max(30).nullable().optional(),
				bullet_points: z.array(z.string().max(2000)).max(20).default([])
			})
		)
		.max(30)
		.default([]),
	education: z
		.array(
			z.object({
				institution_name: z.string().max(300),
				degree_type: z.string().max(200).nullable().optional(),
				field_of_study: z.string().max(250).nullable().optional(),
				start_date: z.string().max(30).nullable().optional(),
				end_date: z.string().max(30).nullable().optional(),
				grade_or_class: z.string().max(120).nullable().optional()
			})
		)
		.max(20)
		.default([]),
	certifications: z
		.array(
			z.object({
				cert_name: z.string().max(300),
				issuing_organization: z.string().max(250).nullable().optional(),
				issue_date: z.string().max(30).nullable().optional(),
				credential_url: z.string().max(1000).nullable().optional()
			})
		)
		.max(30)
		.default([]),
	projects: z
		.array(
			z.object({
				project_name: z.string().max(300),
				description: z.string().max(1500).nullable().optional(),
				tech_stack: z.array(z.string().max(80)).max(20).nullable().optional(),
				project_url: z.string().max(1000).nullable().optional(),
				bullet_points: z.array(z.string().max(2000)).max(20).default([])
			})
		)
		.max(30)
		.default([]),
	skills: z
		.array(
			z.object({
				skill_name: z.string().max(200),
				skill_type: z.string().max(60).nullable().optional()
			})
		)
		.max(200)
		.default([]),
	references: z
		.array(
			z.object({
				name: z.string().max(200),
				role: z.string().max(200).nullable().optional(),
				organisation: z.string().max(250).nullable().optional(),
				email: z.string().max(250).nullable().optional(),
				phone: z.string().max(60).nullable().optional()
			})
		)
		.max(10)
		.optional()
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

function splitName(name: string): { first: string; last: string } {
	const parts = name.trim().split(/\s+/);
	if (parts.length === 0) return { first: '', last: '' };
	return { first: parts[0], last: parts.slice(1).join(' ') };
}

export async function extractResumeProfile(input: {
	name: string;
	email: string;
	resumeText: string;
}): Promise<ResumeProfile | null> {
	const prompt = `Extract this resume into structured JSON. Return only JSON, no markdown fences.

Shape:
{
  "user": {
    "first_name": "...",
    "last_name": "...",
    "email": "...",
    "phone_1": "... or null",
    "phone_2": "... or null",
    "linkedin_url": "... or null",
    "location_city": "... or null",
    "location_country": "... or null"
  },
  "resume": { "professional_summary": "..." },
  "experiences": [
    {
      "company_name": "...",
      "job_title": "...",
      "location": "... or null",
      "start_date": "YYYY-MM or null",
      "end_date": "YYYY-MM or null",
      "bullet_points": ["..."]
    }
  ],
  "education": [
    {
      "institution_name": "...",
      "degree_type": "... or null",
      "field_of_study": "... or null",
      "start_date": "YYYY-MM or null",
      "end_date": "YYYY-MM or null",
      "grade_or_class": "... or null"
    }
  ],
  "certifications": [
    {
      "cert_name": "...",
      "issuing_organization": "... or null",
      "issue_date": "YYYY-MM or null",
      "credential_url": "... or null"
    }
  ],
  "projects": [
    {
      "project_name": "...",
      "description": "... or null",
      "tech_stack": ["..."],
      "project_url": "... or null",
      "bullet_points": ["..."]
    }
  ],
  "skills": [
    { "skill_name": "...", "skill_type": "Language | Framework | Database | Tool | Concept | Soft Skill | ML/AI | DevOps | Other" }
  ],
  "references": [
    {
      "name": "...",
      "role": "job title or relationship, e.g. HOD Humanities",
      "organisation": "... or null",
      "email": "... or null",
      "phone": "... or null"
    }
  ]
}

Rules:
- Use only facts in the resume. Do not invent roles, dates, metrics, tools or skills.
- Preserve every bullet point's facts and metrics; do not merge or embellish.
- Include every work experience, project, qualification and certification.
- Use YYYY-MM dates where possible; null when unknown.
- Prefer the header contact details for email, phone and LinkedIn.
- Capture every referee under "References"/"Referees", including their role, organisation and phone.
- Skills must include the role-specific tools of this person's field, not just generic traits.
  For a teacher that means taught subjects, curricula and exam boards (e.g. ZIMSEC, Cambridge),
  phases taught (ECD, primary, secondary, A Level), and duties (lesson planning, assessment,
  classroom management, syllabus development, co-curriculars). Teaching staff should never end
  up with only soft skills.
  For finance and accounting that means frameworks and standards (IFRS, GAAP), specific
  functions (accounts payable/receivable, general ledger, reconciliations, statutory reporting,
  budgeting, forecasting, variance analysis, payroll, tax compliance, transfer pricing,
  internal controls, audit) and the systems used (SAP, Oracle, Sage Pastel, Pastel Evolution,
  QuickBooks, Excel modelling). Professional designations such as CA, ACCA, CIMA, CPA or CIA
  belong in certifications, not skills.
  Do the same for any other field: capture the recognised competencies of the profession.
- The account name is ${input.name} and the account email is ${input.email}; use them when the resume is ambiguous.

Resume:
${input.resumeText.slice(0, 18000)}`;

	const text = await generateText(prompt, 0.1, 6000);
	if (!text) return null;
	const parsed = profileSchema.safeParse(parseJson(text));
	if (!parsed.success) return null;

	const fallbackName = splitName(input.name);
	const data = parsed.data;
	return {
		user: {
			first_name: data.user.first_name?.trim() || fallbackName.first,
			last_name: data.user.last_name?.trim() || fallbackName.last,
			email: data.user.email?.trim() || input.email,
			phone_1: data.user.phone_1 ?? null,
			phone_2: data.user.phone_2 ?? null,
			linkedin_url: data.user.linkedin_url ?? null,
			location_city: data.user.location_city ?? null,
			location_country: data.user.location_country ?? null
		},
		resume: {
			professional_summary: data.resume.professional_summary ?? null,
			additional_information: data.resume.additional_information ?? null
		},
		experiences: data.experiences,
		education: data.education,
		certifications: data.certifications,
		projects: data.projects,
		skills: data.skills.map((skill) => ({
			skill_name: skill.skill_name,
			skill_type: skill.skill_type ?? 'Other'
		})),
		references: data.references?.map((referee) => ({
			ref_id: crypto.randomUUID(),
			name: referee.name,
			role: referee.role ?? null,
			organisation: referee.organisation ?? null,
			email: referee.email ?? null,
			phone: referee.phone ?? null
		}))
	};
}
