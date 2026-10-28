import type { MatchJob } from '../types';

export const demoJobs: MatchJob[] = [
	{
		id: 'zambezi-graduate-analyst',
		title: 'Graduate Data Analyst',
		company: 'Zambezi Digital Bank',
		location: 'Harare, Zimbabwe',
		salary: 'Competitive graduate package',
		type: 'Graduate programme',
		score: 92,
		summary:
			'Your SQL, Python and dashboard projects map directly to this team reporting pipeline.',
		reasons: [
			'Built ETL pipelines and automated reporting in a previous internship',
			'Strong SQL, Python and dashboard evidence for a graduate programme',
			'The programme targets 0-2 years experience, matching your level'
		],
		skills: ['SQL', 'Python', 'Dashboards', 'ETL', 'Data quality'],
		gaps: ['No formal banking certification', 'Limited cloud data warehouse experience']
	},
	{
		id: 'acacia-mobile-developer',
		title: 'Mobile Developer',
		company: 'Acacia Learning Group',
		location: 'Gweru, Zimbabwe',
		salary: 'TBA',
		type: 'Full time',
		score: 88,
		summary:
			'Flutter, REST APIs and app-store delivery are the core of this role. A completed mobile project is the strongest proof point.',
		reasons: [
			'Built and shipped a cross-platform mobile app',
			'Experience connecting mobile apps to REST APIs',
			'Comfortable with Git and app-store release flows'
		],
		skills: ['Flutter', 'Dart', 'REST APIs', 'Git', 'App-store release'],
		gaps: ['No native iOS/Android production app', 'No formal mobile certification']
	},
	{
		id: 'matobo-data-protection',
		title: 'Data Protection Officer',
		company: 'Matobo Hospitality Group',
		location: 'Harare, Zimbabwe',
		salary: 'TBA',
		type: 'Full time',
		score: 76,
		summary:
			'Compliance and access-control experience is relevant, but the role expects formal privacy or legal experience.',
		reasons: [
			'Handled data-quality and compliance checks',
			'Practical identity and access management exposure',
			'Can translate technical controls into policy language'
		],
		skills: ['Data governance', 'IAM', 'Compliance', 'Risk assessment'],
		gaps: ['No privacy law qualification', 'No DPIA or breach-response track record']
	}
];
