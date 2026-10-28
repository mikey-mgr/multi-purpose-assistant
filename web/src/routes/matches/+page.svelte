<script lang="ts">
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();

	const tabs = $derived([
		{ key: 'active', label: 'Active', count: data.counts.active },
		{ key: 'matched', label: 'Matched', count: data.counts.matched },
		{ key: 'generated', label: 'Generated', count: data.counts.generated },
		{ key: 'applied', label: 'Applied', count: data.counts.applied },
		{ key: 'waiting', label: 'Waiting', count: data.counts.waiting },
		{ key: 'rejected', label: 'Rejected', count: data.counts.rejected },
		{ key: 'all', label: 'All', count: data.counts.all }
	]);

	function statusClass(status: string) {
		if (status === 'applied') return 'bg-match-light text-match-text';
		if (status === 'rejected' || status === 'duplicate') return 'bg-surface-2 text-ink-muted';
		if (status === 'waiting') return 'bg-surface-2 text-warn';
		return 'bg-surface-2 text-ink';
	}
</script>

<svelte:head>
	<title>Matches - Mukana</title>
	<meta name="description" content="All of your Mukana job matches and application stages." />
</svelte:head>

<div class="mx-auto max-w-5xl px-4 py-8 pb-24 sm:px-6">
	<div class="flex flex-wrap items-end justify-between gap-4">
		<div>
			<p class="text-xs font-semibold uppercase tracking-[0.18em] text-brand">Matches</p>
			<h1 class="mt-2 text-3xl font-bold tracking-tight text-ink sm:text-4xl">
				Your application pipeline.
			</h1>
			<p class="mt-2 text-sm text-ink-muted">{data.total} matches in this view.</p>
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
				href={tab.key === 'active' ? '/matches' : `/matches?status=${tab.key}`}
				class="shrink-0 rounded-full border px-3 py-1.5 text-xs font-semibold"
				class:border-brand={data.status === tab.key}
				class:bg-brand={data.status === tab.key}
				class:text-on-brand={data.status === tab.key}
				class:border-line={data.status !== tab.key}
				class:bg-surface={data.status !== tab.key}
				class:text-ink-muted={data.status !== tab.key}
			>
				{tab.label} ({tab.count})
			</a>
		{/each}
	</div>

	{#if data.matches.length === 0}
		<div class="mt-8 rounded-2xl border border-line bg-surface p-8 text-center">
			<h2 class="font-display text-lg font-bold text-ink">Nothing in this stage yet.</h2>
			<p class="mt-2 text-sm text-ink-muted">
				New matches appear after the next scrape and matching run.
			</p>
			<a href="/jobs" class="mt-4 inline-flex text-sm font-semibold text-link">Browse jobs</a>
		</div>
	{:else}
		<div class="mt-5 space-y-3">
			{#each data.matches as match}
				<article class="rounded-2xl border border-line bg-surface p-4 sm:p-5">
					<div class="flex flex-wrap items-start justify-between gap-3">
						<div class="min-w-0">
							<p class="text-xs font-semibold uppercase tracking-[0.16em] text-ink-muted">
								{match.company}
							</p>
							<h2 class="mt-1 font-display text-lg font-bold leading-tight text-ink">
								<a href={`/jobs/${match.jobId}`} class="hover:text-link">{match.title}</a>
							</h2>
							<p class="mt-1 text-xs text-ink-muted">
								{match.location}{match.type ? ` - ${match.type}` : ''}
								{match.compensation ? ` - ${match.compensation}` : ''}
							</p>
						</div>
						<div class="flex shrink-0 items-center gap-2">
							<span class="rounded-full px-2.5 py-1 text-xs font-bold {statusClass(match.status)}">
								{match.status}
							</span>
							{#if match.score !== null}
								<span class="rounded-full bg-match-light px-2.5 py-1 text-xs font-bold text-match-text">
									{match.score}% fit
								</span>
							{/if}
						</div>
					</div>
					{#if match.summary}
						<p class="mt-3 line-clamp-2 text-sm leading-relaxed text-ink-muted">{match.summary}</p>
					{/if}
					<div class="mt-3 flex flex-wrap items-center justify-between gap-3 text-xs text-ink-muted">
						<span>
							{match.action === 'email' && match.recipient
								? `Email: ${match.recipient}`
								: match.action === 'external_link'
									? 'External application'
									: 'Application details pending'}
						</span>
						<a href={`/jobs/${match.jobId}`} class="font-semibold text-link">View role</a>
					</div>
				</article>
			{/each}
		</div>

		<div class="mt-6 flex items-center justify-between gap-3">
			{#if data.page > 1}
				<a
					href={`/matches?status=${data.status}&page=${data.page - 1}`}
					class="text-sm font-semibold text-link">Previous</a
				>
			{:else}
				<span></span>
			{/if}
			<p class="text-xs text-ink-muted">Page {data.page} of {data.pages}</p>
			{#if data.page < data.pages}
				<a
					href={`/matches?status=${data.status}&page=${data.page + 1}`}
					class="text-sm font-semibold text-link">Next</a
				>
			{:else}
				<span></span>
			{/if}
		</div>
	{/if}
</div>
