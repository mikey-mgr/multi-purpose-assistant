<script lang="ts">
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();

	const tabs = $derived([
		{ key: 'all', label: 'All', count: data.counts.all },
		{ key: 'resume', label: 'CVs', count: data.counts.resume },
		{ key: 'cover_letter', label: 'Cover letters', count: data.counts.cover_letter },
		{ key: 'interview_prep', label: 'Interview prep', count: data.counts.interview_prep }
	]);

	function label(type: string) {
		if (type === 'resume') return 'CV';
		if (type === 'cover_letter') return 'Cover letter';
		if (type === 'interview_prep') return 'Interview prep';
		return type;
	}
</script>

<svelte:head>
	<title>Documents - Mukana</title>
	<meta name="description" content="Your tailored CVs, cover letters and interview prep documents." />
</svelte:head>

<div class="mx-auto max-w-4xl px-4 py-8 pb-24 sm:px-6">
	<div class="flex flex-wrap items-end justify-between gap-4">
		<div>
			<p class="text-xs font-semibold uppercase tracking-[0.18em] text-brand">Documents</p>
			<h1 class="mt-2 text-3xl font-bold tracking-tight text-ink sm:text-4xl">
				Your application archive.
			</h1>
			<p class="mt-2 text-sm text-ink-muted">{data.total} documents in this view.</p>
		</div>
		<a
			href="/dashboard"
			class="inline-flex h-10 items-center rounded-full border border-line-strong bg-surface px-4 text-sm font-semibold text-ink hover:bg-surface-2"
		>
			Back to dashboard
		</a>
	</div>

	<div class="mt-5 flex gap-2 overflow-x-auto pb-1">
		{#each tabs as tab}
			<a
				href={tab.key === 'all' ? '/documents' : `/documents?type=${tab.key}`}
				class="shrink-0 rounded-full border px-3 py-1.5 text-xs font-semibold"
				class:border-brand={data.type === tab.key}
				class:bg-brand={data.type === tab.key}
				class:text-on-brand={data.type === tab.key}
				class:border-line={data.type !== tab.key}
				class:bg-surface={data.type !== tab.key}
				class:text-ink-muted={data.type !== tab.key}
			>
				{tab.label} ({tab.count})
			</a>
		{/each}
	</div>

	{#if data.documents.length === 0}
		<div class="mt-8 rounded-2xl border border-line bg-surface p-8 text-center">
			<h2 class="font-display text-lg font-bold text-ink">No documents here yet.</h2>
			<p class="mt-2 text-sm text-ink-muted">
				Tailored documents appear after an application is generated.
			</p>
		</div>
	{:else}
		<div class="mt-5 space-y-2">
			{#each data.documents as document}
				<a
					href={`/documents/${document.id}`}
					class="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-line bg-surface px-4 py-3 hover:border-line-strong"
				>
					<div class="min-w-0">
						<p class="truncate text-sm font-semibold text-ink">
							{label(document.type)} - {document.jobTitle ?? 'General'}
						</p>
						<p class="truncate text-xs text-ink-muted">
							{document.company ?? 'Tailored document'}
						</p>
					</div>
					<span class="text-xs font-semibold text-match-text">Open</span>
				</a>
			{/each}
		</div>

		<div class="mt-6 flex items-center justify-between gap-3">
			{#if data.page > 1}
				<a
					href={`/documents?type=${data.type}&page=${data.page - 1}`}
					class="text-sm font-semibold text-link">Previous</a
				>
			{:else}
				<span></span>
			{/if}
			<p class="text-xs text-ink-muted">Page {data.page} of {data.pages}</p>
			{#if data.page < data.pages}
				<a
					href={`/documents?type=${data.type}&page=${data.page + 1}`}
					class="text-sm font-semibold text-link">Next</a
				>
			{:else}
				<span></span>
			{/if}
		</div>
	{/if}
</div>
