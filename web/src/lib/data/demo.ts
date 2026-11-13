import type { MatchJob } from '../types';

export const demoJobs: MatchJob[] = [
	{
		id: 'accounts-assistant',
		title: 'Accounts Assistant',
		company: 'Harare Retail Group',
		location: 'Harare, Zimbabwe',
		salary: 'USD 350 - 450 / month',
		type: 'Full time',
		score: 86,
		summary:
			'Your bookkeeping, Excel and reconciliation experience fit this finance team.',
		reasons: [
			'Handled cash reconciliations and monthly reports',
			'Comfortable with Excel formulas and stock records',
			'Role open to candidates with 1-2 years experience'
		],
		skills: ['Bookkeeping', 'Excel', 'Reconciliations', 'Stock records'],
		gaps: ['No Pastel certification', 'Limited payroll exposure']
	},
	{
		id: 'sales-representative',
		title: 'Sales Representative',
		company: 'Bulawayo Road Distributors',
		location: 'Harare, Zimbabwe',
		salary: 'Base + commission',
		type: 'Full time',
		score: 82,
		summary:
			'Your customer service and field sales experience fit this FMCG distributor.',
		reasons: [
			'Experience building customer relationships',
			'Comfortable working to weekly and monthly targets',
			'Role includes local field travel'
		],
		skills: ['Field sales', 'Customer service', 'Negotiation', 'Targets'],
		gaps: ['No formal sales qualification', 'No FMCG product experience']
	},
	{
		id: 'administrative-assistant',
		title: 'Administrative Assistant',
		company: 'Avondale Medical Practice',
		location: 'Harare, Zimbabwe',
		salary: 'USD 300 - 400 / month',
		type: 'Full time',
		score: 79,
		summary:
			'Your office administration, scheduling and records experience fit this practice.',
		reasons: [
			'Experience managing schedules and client records',
			'Comfortable with Microsoft Office and email',
			'Role values accuracy and confidentiality'
		],
		skills: ['Office administration', 'Scheduling', 'Records', 'MS Office'],
		gaps: ['No medical reception experience', 'No first-aid certificate']
	}
];
