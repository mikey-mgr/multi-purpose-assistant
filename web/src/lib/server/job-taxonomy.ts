import { sql, type SQL } from 'drizzle-orm';

/**
 * Canonical role families for market reporting.
 *
 * The raw `jobs.category` column is whatever each board called it: vacancymail
 * emits "Accounting & Finance Jobs", iharare emits the employer's name, and
 * applynow emits a location. These helpers fold that into a small, stable set
 * so aggregates are comparable, and treat anything unrecognisable as
 * "Uncategorised" rather than inventing a family from an employer name.
 */
export const ROLE_FAMILIES = [
	'Technology',
	'Finance & accounting',
	'Banking',
	'Sales & marketing',
	'Education & teaching',
	'Engineering',
	'Admin & office',
	'Healthcare',
	'NGO & social services',
	'Agriculture',
	'Logistics & driving',
	'Hospitality & tourism',
	'Human resources',
	'Legal',
	'Mining',
	'Construction',
	'Manufacturing',
	'Procurement & supply chain',
	'Security',
	'Media & communications',
	'Research & consultancy'
] as const;

export type RoleFamily = (typeof ROLE_FAMILIES)[number];

/**
 * SQL expression mapping a raw category to a canonical family.
 *
 * Order matters: the more specific patterns must come before the general ones
 * ("construction & civil engineering" before "engineering").
 */
export function familySql(categoryColumn: SQL | string = sql`category`): SQL {
	const c = sql`lower(coalesce(${categoryColumn}, ''))`;

	return sql`case
		when ${c} like '%ict%' or ${c} like '%computer%' or ${c} like '%information tech%' then 'Technology'
		when ${c} like '%accounting%' or ${c} like '%finance%' then 'Finance & accounting'
		when ${c} like '%banking%' then 'Banking'
		when ${c} like '%sales%' or ${c} like '%marketing jobs%' then 'Sales & marketing'
		when ${c} like '%education%' or ${c} like '%teaching%' then 'Education & teaching'
		when ${c} like '%construction%' or ${c} like '%civil engine%' then 'Construction'
		when ${c} like '%engineering%' or ${c} like '%mechanical%' then 'Engineering'
		when ${c} like '%admin%' or ${c} like '%office jobs%' or ${c} like '%secretar%' then 'Admin & office'
		when ${c} like '%nursing%' or ${c} like '%health%' or ${c} like '%pharmac%' or ${c} like '%doctor%' then 'Healthcare'
		when ${c} like '%ngo%' or ${c} like '%social service%' or ${c} like '%humanitarian%' then 'NGO & social services'
		when ${c} like '%agricultur%' or ${c} like '%farming%' or ${c} like '%environmental%' then 'Agriculture'
		when ${c} like '%driving%' or ${c} like '%logistic%' or ${c} like '%transport%' or ${c} like '%stores%' or ${c} like '%warehouse%' then 'Logistics & driving'
		when ${c} like '%tourism%' or ${c} like '%hospitality%' or ${c} like '%hotel%' then 'Hospitality & tourism'
		when ${c} like '%human resources%' or ${c} like '%hr jobs%' then 'Human resources'
		when ${c} like '%legal%' then 'Legal'
		when ${c} like '%mining%' then 'Mining'
		when ${c} like '%manufactur%' then 'Manufacturing'
		when ${c} like '%procurement%' or ${c} like '%supply chain%' or ${c} like '%purchasing%' then 'Procurement & supply chain'
		when ${c} like '%security%' then 'Security'
		when ${c} like '%media%' or ${c} like '%communication%' or ${c} like '%graphic design%' then 'Media & communications'
		when ${c} like '%consultancy%' or ${c} like '%research%' then 'Research & consultancy'
		else 'Uncategorised'
	end`;
}

/**
 * SQL expression mapping the free-text job_type to a small enum.
 *
 * Several boards stuff the first paragraph of the description into job_type,
 * so match on keywords anywhere in the string rather than comparing equality.
 */
export function jobTypeSql(jobTypeColumn: SQL | string = sql`job_type`): SQL {
	const t = sql`lower(coalesce(${jobTypeColumn}, ''))`;

	return sql`case
		when ${jobTypeColumn} is null or ${jobTypeColumn} in ('', 'NaN', 'nan', 'Unknown', 'Not specified') then 'Unspecified'
		when ${t} like '%intern%' or ${t} like '%attachment%' or ${t} like '%graduate trainee%' or ${t} like '%work-related learning%' then 'Internship'
		when ${t} like '%part time%' or ${t} like '%part-time%' then 'Part-time'
		when ${t} like '%fixed term%' or ${t} like '%fixed-term%' or ${t} like '%contract%' or ${t} like '%consultanc%' then 'Contract'
		when ${t} like '%full time%' or ${t} like '%full-time%' or ${t} like '%permanent%' then 'Full-time'
		when ${t} like '%remote%' then 'Remote'
		when ${t} like '%field-based%' or ${t} like '%field based%' then 'Field-based'
		else 'Other'
	end`;
}

/**
 * SQL predicate: is this a genuine role category, or board noise such as an
 * employer name ("Midlands State University") or a location ("Zimbabwe")?
 */
export function isCategorySql(categoryColumn: SQL | string = sql`category`): SQL {
	const c = sql`lower(coalesce(${categoryColumn}, ''))`;

	return sql`(
		${categoryColumn} is not null
		and ${categoryColumn} not in ('', 'NaN', 'nan')
		and ${c} not like '%university%'
		and ${c} not like '%college%'
		and ${c} not like '%polytechnic%'
		and ${c} not like '%zimbabwe, zimbabwe%'
		and ${c} not like '%remote, remote%'
		and ${c} not like '%iharare jobs%'
		and ${c} not like '%tenders%'
		and ${c} not like '%she jobs%'
	)`;
}
