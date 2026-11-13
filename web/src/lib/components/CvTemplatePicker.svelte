<script lang="ts">
	import { CV_TEMPLATES, type CvTemplate } from '../cv-templates';

	let {
		value = 'harvard',
		onchange
	}: {
		value?: CvTemplate | string;
		onchange?: (template: CvTemplate) => void;
	} = $props();

	let selected = $state<string>(value);
	$effect(() => {
		selected = value;
	});

	const DESCRIPTIONS: Record<string, string> = {
		harvard: 'Centred name, blue rules, classic academic layout',
		classic: 'Traditional serif CV with a clean single column',
		moderncv: 'Modern with a coloured header and tighter spacing',
		sb2nov: 'Compact, dense, built for technical roles',
		engineeringclassic: 'Engineering-focused with emphasised skills',
		engineeringresumes: 'ATS-friendly engineering format',
		ember: 'Warm accent colour with decorative headings',
		ink: 'High-contrast, minimal, editorial feel',
		opal: 'Soft pastel accents, airy spacing'
	};

	function pick(template: CvTemplate) {
		selected = template;
		onchange?.(template);
	}
</script>

<input type="hidden" name="cvTemplate" value={selected} />

<div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
	{#each CV_TEMPLATES as template}
		{@const active = selected === template.value}
		<button
			type="button"
			onclick={() => pick(template.value)}
			aria-pressed={active}
			class="group relative overflow-hidden rounded-2xl border-2 bg-surface text-left transition-all {active
				? 'border-brand ring-2 ring-brand/25'
				: 'border-line hover:border-line-strong hover:shadow-md'}"
		>
			<div class="relative aspect-[3/4] overflow-hidden bg-white">
				<img
					src={`/cv-templates/${template.value}.png`}
					alt={`${template.label} CV template preview`}
					loading="lazy"
					class="size-full object-cover object-top transition-transform duration-300 group-hover:scale-[1.02]"
				/>
				{#if active}
					<span
						class="absolute right-2 top-2 flex size-7 items-center justify-center rounded-full bg-brand text-on-brand shadow"
					>
						<svg viewBox="0 0 20 20" fill="currentColor" class="size-4" aria-hidden="true">
							<path
								fill-rule="evenodd"
								d="M16.7 5.3a1 1 0 0 1 0 1.4l-7.5 7.5a1 1 0 0 1-1.4 0l-3.5-3.5a1 1 0 1 1 1.4-1.4l2.8 2.8 6.8-6.8a1 1 0 0 1 1.4 0Z"
								clip-rule="evenodd"
							/>
						</svg>
					</span>
				{/if}
			</div>
			<div class="border-t border-line px-3 py-2.5">
				<p class="text-sm font-semibold text-ink">{template.label}</p>
				<p class="mt-0.5 text-xs leading-snug text-ink-muted">
					{DESCRIPTIONS[template.value] ?? ''}
				</p>
			</div>
		</button>
	{/each}
</div>
