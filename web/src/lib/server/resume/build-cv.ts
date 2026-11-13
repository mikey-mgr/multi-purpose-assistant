import type { ProfileReference, ResumeOverrides, ResumeProfile } from './types';

export type RenderCvData = {
	name: string;
	location?: string;
	email?: string;
	phone?: string;
	social_networks?: Array<{ network: string; username: string }>;
	sections: Record<string, unknown[]>;
};

const MONTHS: Record<string, string> = {
	jan: '01',
	feb: '02',
	mar: '03',
	apr: '04',
	may: '05',
	jun: '06',
	jul: '07',
	aug: '08',
	sep: '09',
	oct: '10',
	nov: '11',
	dec: '12'
};

function monthNumber(value: number): string {
	return String(Math.min(12, Math.max(1, value))).padStart(2, '0');
}

function formatDate(
	value: string | null | undefined,
	kind: 'start' | 'end' = 'start'
): string | null {
	if (!value) return null;
	const text = String(value).trim();
	if (!text || /^(present|current|now|ongoing)$/i.test(text)) return null;

	const iso = text.match(/^(\d{4})-(\d{1,2})(?:-\d{1,2})?/);
	if (iso) return `${iso[1]}-${monthNumber(Number(iso[2]))}`;

	const yearOnly = text.match(/^(\d{4})$/);
	if (yearOnly) return `${yearOnly[1]}-${kind === 'end' ? '12' : '01'}`;

	const slash = text.match(/^(\d{1,2})\/(\d{4})$/);
	if (slash) return `${slash[2]}-${monthNumber(Number(slash[1]))}`;

	const yearSlash = text.match(/^(\d{4})\/(\d{1,2})$/);
	if (yearSlash) return `${yearSlash[1]}-${monthNumber(Number(yearSlash[2]))}`;

	const monthYear = text.match(/^([A-Za-z]{3,9})\s+(\d{4})$/);
	if (monthYear) {
		const month = MONTHS[monthYear[1].slice(0, 3).toLowerCase()];
		if (month) return `${monthYear[2]}-${month}`;
	}

	return null;
}

function normalizeUrl(value: string | null | undefined): string | null {
	if (!value) return null;
	const text = value.trim();
	if (!text) return null;
	return /^[a-zA-Z][a-zA-Z0-9+.-]*:\/\//.test(text) ? text : `https://${text}`;
}

function linkedinUsername(value: string | null | undefined): string | null {
	if (!value) return null;
	return value.replace(/^https?:\/\//i, '').replace(/\/$/, '');
}

function groupSkills(skills: ResumeProfile['skills']): Array<{ label: string; details: string }> {
	const groups = new Map<string, string[]>();
	for (const skill of skills) {
		const type = skill.skill_type || 'Other';
		const bucket = groups.get(type) ?? [];
		bucket.push(skill.skill_name);
		groups.set(type, bucket);
	}

	const categories: Array<[string, string[]]> = [
		['Languages', ['Language']],
		['Frameworks & Libraries', ['Framework', 'ML/AI']],
		['DevOps & Tools', ['DevOps', 'Tool']],
		['Databases', ['Database']],
		['Concepts', ['Concept']],
		// The extractor often returns the looser Hard/Soft Split, so keep those
		// readable instead of dumping every skill into one unlabelled block.
		['Technical Skills', ['Hard Skill']],
		['Soft Skills', ['Soft Skill']]
	];
	const rows: Array<{ label: string; details: string }> = [];
	const consumed = new Set<string>();
	for (const [label, types] of categories) {
		const items = types.flatMap((type) => groups.get(type) ?? []);
		for (const type of types) consumed.add(type);
		if (items.length) rows.push({ label, details: items.join(', ') });
	}
	for (const [label, items] of groups) {
		if (!consumed.has(label) && items.length) {
			rows.push({ label, details: items.join(', ') });
		}
	}
	return rows;
}

function overrideKey(
	map: Record<string, string[]> | undefined,
	key: string
): string[] | null {
	if (!map) return null;
	if (map[key]) return map[key];
	const target = key.toLowerCase();
	const match = Object.keys(map).find((candidate) => candidate.toLowerCase() === target);
	return match ? map[match] : null;
}

export function buildCvData(
	profile: ResumeProfile,
	overrides: ResumeOverrides,
	options: { references?: ProfileReference[]; referencesEnabled?: boolean } = {}
): RenderCvData {
	const user = profile.user;
	const name = `${user.first_name ?? ''} ${user.last_name ?? ''}`.trim() || 'Candidate';
	const location = [user.location_city, user.location_country].filter(Boolean).join(', ');
	const sections: Record<string, unknown[]> = {};

	const summary = overrides.summary?.trim() || profile.resume.professional_summary?.trim();
	if (summary) sections['Professional Summary'] = [summary];

	const skills = overrides.skills?.length ? overrides.skills : groupSkills(profile.skills);
	if (skills.length) sections['Skills'] = skills;

	const experience = profile.experiences.map((item) => ({
		company: item.company_name,
		position: item.job_title,
		location: item.location || null,
		start_date: formatDate(item.start_date, 'start'),
		end_date: formatDate(item.end_date, 'end'),
		highlights:
			overrideKey(overrides.experience_highlights, `${item.company_name} - ${item.job_title}`) ??
			item.bullet_points
	}));
	if (experience.length) sections['Experience'] = experience;

	const education = profile.education.map((item) => ({
		institution: item.institution_name,
		area: item.field_of_study || null,
		degree: item.degree_type || null,
		start_date: formatDate(item.start_date, 'start'),
		end_date: formatDate(item.end_date, 'end'),
		highlights: item.grade_or_class ? [`Grade: ${item.grade_or_class}`] : null
	}));
	if (education.length) sections['Education'] = education;

	const certifications = profile.certifications.map((item) => ({
		name: item.credential_url
			? `[${item.cert_name} (Click to view)](${normalizeUrl(item.credential_url)})`
			: item.cert_name,
		issuer: item.issuing_organization || null,
		date: formatDate(item.issue_date, 'start')
	}));
	if (certifications.length) sections['Certifications'] = certifications;

	const projectOverrides = overrides.project_highlights ?? {};
	const overrideNames = Object.keys(projectOverrides);
	const matchedProjects = overrideNames.length
		? profile.projects.filter((project) =>
				overrideNames.some(
					(nameOverride) =>
						nameOverride.toLowerCase() === project.project_name.toLowerCase()
				)
			)
		: [];
	const selectedProjects = matchedProjects.length
		? matchedProjects
		: [...profile.projects].slice(0, 2);

	const projects = selectedProjects.map((project) => ({
		name: project.project_url
			? `[${project.project_name} (Click to view)](${normalizeUrl(project.project_url)})`
			: project.project_name,
		summary: project.tech_stack?.length ? `*Tech:* ${project.tech_stack.join(' · ')}` : null,
		highlights:
			overrideKey(projectOverrides, project.project_name) ?? project.bullet_points
	}));
	if (projects.length) sections['Projects'] = projects;

	const referees = options.referencesEnabled ? (options.references ?? []) : [];
	if (referees.length) {
		sections['References'] = referees.map((referee) => {
			const contact = [referee.email, referee.phone].filter(Boolean).join(' | ');
			const heading = [referee.name, referee.role].filter(Boolean).join(', ');
			return {
				name: heading,
				summary: [referee.organisation, contact].filter(Boolean).join(' - ') || null
			};
		});
	} else {
		sections['References'] = ['Available upon request'];
	}

	return {
		name,
		location: location || undefined,
		email: user.email || undefined,
		phone: user.phone_1 || user.phone_2 || undefined,
		social_networks: user.linkedin_url
			? [{ network: 'LinkedIn', username: linkedinUsername(user.linkedin_url) ?? '' }]
			: undefined,
		sections
	};
}
