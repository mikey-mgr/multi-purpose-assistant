export type { CvTemplate } from '../../cv-templates';
export { CV_TEMPLATES } from '../../cv-templates';

export type ResumeExperience = {
	company_name: string;
	job_title: string;
	location?: string | null;
	start_date?: string | null;
	end_date?: string | null;
	bullet_points: string[];
};

export type ResumeEducation = {
	institution_name: string;
	degree_type?: string | null;
	field_of_study?: string | null;
	start_date?: string | null;
	end_date?: string | null;
	grade_or_class?: string | null;
};

export type ResumeCertification = {
	cert_name: string;
	issuing_organization?: string | null;
	issue_date?: string | null;
	credential_url?: string | null;
};

export type ResumeProject = {
	project_name: string;
	description?: string | null;
	tech_stack?: string[] | null;
	project_url?: string | null;
	bullet_points: string[];
};

/** A referee saved on the profile, shown on a CV only when references are enabled. */
export type ProfileReference = {
	id: string;
	name: string;
	role?: string | null;
	organisation?: string | null;
	email?: string | null;
	phone?: string | null;
};

export type ResumeProfile = {
	user: {
		first_name: string;
		last_name: string;
		email: string;
		phone_1?: string | null;
		phone_2?: string | null;
		linkedin_url?: string | null;
		location_city?: string | null;
		location_country?: string | null;
	};
	resume: {
		professional_summary?: string | null;
		additional_information?: Record<string, unknown> | null;
	};
	experiences: ResumeExperience[];
	education: ResumeEducation[];
	certifications: ResumeCertification[];
	projects: ResumeProject[];
	skills: Array<{ skill_name: string; skill_type?: string | null }>;
	documents?: Record<string, string>;
	references?: Array<{
		ref_id?: string;
		name: string;
		role?: string | null;
		organisation?: string | null;
		email?: string | null;
		phone?: string | null;
		description?: string | null;
	}>;
};

export type ResumeOverrides = {
	summary?: string;
	skills?: Array<{ label: string; details: string }>;
	experience_highlights?: Record<string, string[]>;
	project_highlights?: Record<string, string[]>;
	references?: Array<{ ref_id?: string; name: string; description?: string | null }> | null;
};

export type ApplyDetails = {
	action?: 'email' | 'external_link' | 'unknown';
	recipient?: string | null;
	subject?: string | null;
	body?: string | null;
	url?: string | null;
	required_docs?: string[];
	proceed?: 'apply_now' | 'needs_docs' | 'needs_info';
	expiry_date?: string | null;
	merged_pdf?: boolean;
};

export type TailoredApplication = {
	resume: ResumeOverrides;
	coverLetter: string | null;
	applyDetails: ApplyDetails;
	missingResources: string | null;
};
