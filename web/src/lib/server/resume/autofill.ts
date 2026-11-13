import type { ResumeProfile } from './types';

export type AutofillSuggestions = {
	headline: string | null;
	location: string | null;
	yearsExperience: number | null;
	phone: string | null;
	linkedinUrl: string | null;
	targetFamilies: string[];
};

const FAMILY_KEYWORDS: Array<{ family: string; keywords: string[] }> = [
	{ family: 'software', keywords: ['software developer', 'software engineer', 'frontend', 'backend', 'full stack', 'fullstack', 'programmer', 'web developer', 'react', 'node.js', 'laravel'] },
	{ family: 'data', keywords: ['data analyst', 'data scientist', 'data analytics', 'business intelligence', 'power bi', 'tableau', 'data engineer', 'machine learning', 'monitoring and evaluation', 'm&e officer', 'statistician'] },
	{ family: 'it_support', keywords: ['it support', 'ict officer', 'helpdesk', 'help desk', 'desktop support', 'systems administrator', 'system administrator', 'network administrator', 'ict technician'] },
	{ family: 'cyber', keywords: ['cyber security', 'cybersecurity', 'information security', 'infosec', 'penetration test', 'soc analyst'] },
	{ family: 'compliance', keywords: ['compliance officer', 'data protection', 'governance', 'internal audit', 'risk management', 'corporate governance', 'regulatory'] },
	{ family: 'sales', keywords: ['sales representative', 'sales manager', 'business development', 'account manager', 'merchandiser'] },
	{ family: 'teaching', keywords: ['teacher', 'teaching', 'lecturer', 'tutor', 'educator', 'head of department', 'curriculum', 'lesson plan', 'classroom', 'zimsec', 'pedagogy', 'postgraduate diploma in education'] },
	{ family: 'electronics', keywords: ['electronics', 'cctv', 'electrical technician', 'instrumentation'] },
	{ family: 'admin', keywords: ['administrator', 'administrative', 'office manager', 'secretary', 'receptionist', 'operations coordinator', 'data entry clerk'] },
	{ family: 'finance', keywords: ['chartered accountant', 'finance manager', 'finance director', 'financial controller', 'chief accountant', 'accounts payable', 'accounts receivable', 'financial reporting', 'ifrs', 'budgeting', 'forecasting', 'tax compliance', 'transfer pricing', 'payroll', 'bookkeeper', 'auditor', 'internal audit', 'external audit', 'sage pastel', 'pastel', 'statutory reporting', 'variance analysis', 'cash flow', 'general ledger', 'reconciliation'] },
	{ family: 'banking', keywords: ['banking', 'bank officer', 'fintech', 'credit analyst', 'loan officer', 'treasury'] },
	{ family: 'hr', keywords: ['human resources', 'hr officer', 'hr manager', 'recruitment', 'recruiter', 'talent acquisition', 'industrial relations'] },
	{ family: 'marketing', keywords: ['marketing', 'communications officer', 'brand manager', 'social media', 'content creator', 'digital marketing', 'public relations'] },
	{ family: 'legal', keywords: ['legal officer', 'lawyer', 'attorney', 'advocate', 'paralegal', 'litigation'] },
	{ family: 'healthcare', keywords: ['nurse', 'nursing', 'clinical officer', 'medical doctor', 'pharmacist', 'midwife', 'primary health care'] },
	{ family: 'engineering', keywords: ['civil engineer', 'mechanical engineer', 'electrical engineer', 'structural engineer', 'site engineer'] },
	{ family: 'mining', keywords: ['mining engineer', 'geologist', 'mine planning', 'mineral processing'] },
	{ family: 'agriculture', keywords: ['agricultural officer', 'agronomist', 'livestock', 'horticulture', 'crop production', 'farming'] },
	{ family: 'logistics', keywords: ['logistics officer', 'supply chain', 'procurement officer', 'warehouse manager', 'stores controller', 'fleet management'] },
	{ family: 'hospitality', keywords: ['hospitality', 'tourism', 'hotel manager', 'restaurant', 'chef', 'housekeeping'] },
	{ family: 'customer_service', keywords: ['customer service', 'customer care', 'call center', 'call centre', 'client service'] },
	{ family: 'trades', keywords: ['welder', 'plumber', 'carpenter', 'electrician', 'mechanic', 'fitter', 'boilermaker'] }
];

function cleanValue(value: string | null | undefined): string | null {
	if (!value) return null;
	const trimmed = value.trim();
	return trimmed && trimmed.toLowerCase() !== 'null' ? trimmed : null;
}

/** Pull a "YYYY-MM" or "YYYY" date into a year number. */
function yearOf(value: string | null | undefined): number | null {
	const match = cleanValue(value)?.match(/(19|20)\d{2}/);
	if (!match) return null;
	const year = Number(match[0]);
	return year > 1940 && year <= new Date().getFullYear() + 1 ? year : null;
}

function yearsSince(profile: ResumeProfile): number | null {
	const starts = profile.experiences
		.map((experience) => yearOf(experience.start_date))
		.filter((year): year is number => year !== null);
	if (starts.length === 0) return null;

	const earliest = Math.min(...starts);
	const years = new Date().getFullYear() - earliest;
	return Math.max(0, Math.min(50, years));
}

function headlineFrom(profile: ResumeProfile): string | null {
	const sorted = [...profile.experiences].sort((a, b) => {
		const aEnd = yearOf(a.end_date) ?? new Date().getFullYear();
		const bEnd = yearOf(b.end_date) ?? new Date().getFullYear();
		return bEnd - aEnd;
	});
	const latestTitle = cleanValue(sorted[0]?.job_title);
	const summary = cleanValue(profile.resume.professional_summary);

	if (latestTitle && summary) {
		const focus = summary.split(/[.;]/)[0]?.trim().slice(0, 60);
		return focus && !focus.toLowerCase().includes(latestTitle.toLowerCase())
			? `${latestTitle} - ${focus}`.slice(0, 160)
			: latestTitle.slice(0, 160);
	}
	if (latestTitle) return latestTitle.slice(0, 160);
	if (summary) return summary.slice(0, 160);

	const topSkills = profile.skills.slice(0, 3).map((skill) => skill.skill_name);
	return topSkills.length ? topSkills.join(', ').slice(0, 160) : null;
}

function locationFrom(profile: ResumeProfile): string | null {
	const city = cleanValue(profile.user.location_city);
	const country = cleanValue(profile.user.location_country);
	if (city && country) return `${city}, ${country}`.slice(0, 120);
	if (city) return city.slice(0, 120);
	if (country) return country.slice(0, 120);
	return null;
}

function familiesFrom(profile: ResumeProfile): string[] {
	const haystack = [
		...profile.experiences.map((experience) => `${experience.job_title} ${experience.company_name}`),
		profile.resume.professional_summary ?? '',
		...profile.skills.map((skill) => skill.skill_name),
		...profile.education.map((entry) => `${entry.degree_type ?? ''} ${entry.field_of_study ?? ''}`)
	]
		.join(' ')
		.toLowerCase();

	const matched: string[] = [];
	for (const { family, keywords } of FAMILY_KEYWORDS) {
		if (keywords.some((keyword) => haystack.includes(keyword))) matched.push(family);
	}
	return matched.slice(0, 8);
}

/**
 * Turn an extracted CV into the onboarding fields, so a user can upload once
 * and review pre-filled values instead of retyping their history.
 */
export function buildAutofillSuggestions(profile: ResumeProfile): AutofillSuggestions {
	return {
		headline: headlineFrom(profile),
		location: locationFrom(profile),
		yearsExperience: yearsSince(profile),
		phone: cleanValue(profile.user.phone_1),
		linkedinUrl: cleanValue(profile.user.linkedin_url),
		targetFamilies: familiesFrom(profile)
	};
}
