export type CvTemplate =
	| 'harvard'
	| 'classic'
	| 'moderncv'
	| 'sb2nov'
	| 'engineeringclassic'
	| 'engineeringresumes'
	| 'ember'
	| 'ink'
	| 'opal';

export const CV_TEMPLATES: Array<{ value: CvTemplate; label: string }> = [
	{ value: 'harvard', label: 'Harvard' },
	{ value: 'classic', label: 'Classic' },
	{ value: 'moderncv', label: 'Modern CV' },
	{ value: 'sb2nov', label: 'SB2Nov' },
	{ value: 'engineeringclassic', label: 'Engineering Classic' },
	{ value: 'engineeringresumes', label: 'Engineering Resumes' },
	{ value: 'ember', label: 'Ember' },
	{ value: 'ink', label: 'Ink' },
	{ value: 'opal', label: 'Opal' }
];

export const CV_TEMPLATE_VALUES = CV_TEMPLATES.map((template) => template.value) as [
	CvTemplate,
	...CvTemplate[]
];
