export type MatchJob = {
	id: string;
	title: string;
	company: string;
	location: string;
	salary?: string;
	type?: string;
	score: number;
	summary: string;
	reasons: string[];
	skills: string[];
	gaps: string[];
	href?: string;
};
