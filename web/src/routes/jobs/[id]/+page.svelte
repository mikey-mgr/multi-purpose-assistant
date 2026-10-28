<script lang="ts">
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();
</script>

<svelte:head>
	<title>{data.job.title} - Mukana</title>
	<meta name="description" content={`${data.job.title} at ${data.job.company}`} />
</svelte:head>

<div class="mx-auto max-w-3xl px-4 py-8 pb-24 sm:px-6">
	<a href="/jobs" class="text-sm font-semibold text-link">Back to jobs</a>

	<div class="mt-5 rounded-2xl border border-line bg-surface p-6 sm:p-8">
		<p class="text-xs font-semibold uppercase tracking-[0.18em] text-ink-muted">{data.job.company}</p>
		<h1 class="mt-2 font-display text-3xl font-bold tracking-tight text-ink sm:text-4xl">
			{data.job.title}
		</h1>
		<p class="mt-3 text-sm text-ink-muted">
			{data.job.location}{data.job.type ? ` - ${data.job.type}` : ''}{data.job.remote ? ' - Remote' : ''}
		</p>

		<div class="mt-5 flex flex-wrap gap-2">
			{#if data.job.compensation}
				<span class="rounded-full bg-surface-2 px-3 py-1 text-xs font-semibold text-ink-muted">
					{data.job.compensation}
				</span>
			{/if}
			{#if data.job.category}
				<span class="rounded-full bg-surface-2 px-3 py-1 text-xs font-semibold text-ink-muted">
					{data.job.category}
				</span>
			{/if}
			{#if data.job.datePosted}
				<span class="rounded-full bg-surface-2 px-3 py-1 text-xs font-semibold text-ink-muted">
					Posted {data.job.datePosted}
				</span>
			{/if}
			{#if data.job.expires}
				<span class="rounded-full bg-surface-2 px-3 py-1 text-xs font-semibold text-ink-muted">
					Closes {data.job.expires}
				</span>
			{/if}
		</div>

		<section class="mt-7">
			<h2 class="font-display text-lg font-bold text-ink">Role summary</h2>
			<p class="mt-2 whitespace-pre-wrap text-sm leading-relaxed text-ink-muted">{data.job.summary}</p>
		</section>

		{#if data.job.applyInstructions}
			<section class="mt-6">
				<h2 class="font-display text-lg font-bold text-ink">How to apply</h2>
				<p class="mt-2 whitespace-pre-wrap text-sm leading-relaxed text-ink-muted">
					{data.job.applyInstructions}
				</p>
			</section>
		{/if}

		<div class="mt-8 flex flex-wrap gap-3">
			<a
				href="/dashboard"
				class="inline-flex h-11 items-center justify-center rounded-full bg-brand px-5 text-sm font-semibold text-on-brand hover:bg-brand-hover"
			>
				See my matches
			</a>
			<a
				href="/jobs"
				class="inline-flex h-11 items-center justify-center rounded-full border border-line-strong bg-surface px-5 text-sm font-semibold text-ink hover:bg-surface-2"
			>
				Browse more roles
			</a>
		</div>
	</div>
</div>
