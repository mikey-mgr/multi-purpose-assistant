export type RoleFamily =
	| 'software'
	| 'data'
	| 'it_support'
	| 'cyber'
	| 'sales'
	| 'teaching'
	| 'compliance'
	| 'electronics'
	| 'admin'
	| 'finance'
	| 'banking'
	| 'hr'
	| 'marketing'
	| 'legal'
	| 'healthcare'
	| 'engineering'
	| 'mining'
	| 'agriculture'
	| 'logistics'
	| 'hospitality'
	| 'customer_service'
	| 'trades'
	| 'other';

export type RoleFamilyGroup = {
	value: string;
	label: string;
	hint: string;
	families: Array<{ value: RoleFamily; label: string }>;
};

/**
 * Grouped for the picker so 23 fields are not shown as one wall of checkboxes.
 * The flat list stays the source of truth for validation.
 */
export const ROLE_FAMILY_GROUPS: RoleFamilyGroup[] = [
	{
		value: 'tech',
		label: 'Technology',
		hint: 'Software, data, IT, security',
		families: [
			{ value: 'software', label: 'Software & mobile' },
			{ value: 'data', label: 'Data & analytics' },
			{ value: 'it_support', label: 'IT support' },
			{ value: 'cyber', label: 'Cyber security' },
			{ value: 'electronics', label: 'Electronics & CCTV' }
		]
	},
	{
		value: 'business',
		label: 'Business & finance',
		hint: 'Finance, banking, admin, sales',
		families: [
			{ value: 'finance', label: 'Finance & accounting' },
			{ value: 'banking', label: 'Banking & fintech' },
			{ value: 'admin', label: 'Admin & operations' },
			{ value: 'sales', label: 'Sales & field' },
			{ value: 'hr', label: 'HR & recruiting' },
			{ value: 'marketing', label: 'Marketing & communications' }
		]
	},
	{
		value: 'public',
		label: 'Education & public service',
		hint: 'Teaching, legal, healthcare',
		families: [
			{ value: 'teaching', label: 'Teaching & education' },
			{ value: 'legal', label: 'Legal & regulatory' },
			{ value: 'compliance', label: 'Compliance & data protection' },
			{ value: 'healthcare', label: 'Healthcare & medical' }
		]
	},
	{
		value: 'industry',
		label: 'Industry & trades',
		hint: 'Engineering, mining, logistics',
		families: [
			{ value: 'engineering', label: 'Engineering' },
			{ value: 'mining', label: 'Mining & geology' },
			{ value: 'agriculture', label: 'Agriculture & environment' },
			{ value: 'logistics', label: 'Logistics & supply chain' },
			{ value: 'trades', label: 'Skilled trades' }
		]
	},
	{
		value: 'service',
		label: 'Service & hospitality',
		hint: 'Customer service, tourism',
		families: [
			{ value: 'customer_service', label: 'Customer service' },
			{ value: 'hospitality', label: 'Hospitality & tourism' },
			{ value: 'other', label: 'Other' }
		]
	}
];

export const ROLE_FAMILIES: RoleFamily[] = ROLE_FAMILY_GROUPS.flatMap((group) =>
	group.families.map((family) => family.value)
);
