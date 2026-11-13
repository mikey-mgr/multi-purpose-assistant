<script lang="ts">
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();

	const query = $derived(
		[
			data.q ? `q=${encodeURIComponent(data.q)}` : '',
			data.category ? `category=${encodeURIComponent(data.category)}` : '',
			data.location ? `location=${encodeURIComponent(data.location)}` : '',
			data.fresh ? 'fresh=today' : ''
		]
			.filter(Boolean)
			.join('&')
	);

	function pageHref(page: number) {
		return `/jobs?${[query, `page=${page}`].filter(Boolean).join('&')}`;
	}
</script>

<svelte:head>
	<title>Jobs - Mukana</title>
	<meta name="description" content="Search live local and remote job listings in the Mukana workspace." />
</svelte:head>

<div class="mx-auto max-w-6xl px-4 py-8 pb-24 sm:px-6">
	<div class="flex flex-wrap items-end justify-between gap-4">
		<div>
			<p class="text-xs font-semibold uppercase tracking-[0.18em] text-brand">Job feed</p>
			<h1 class="mt-2 text-3xl font-bold tracking-tight text-ink sm:text-4xl">
				Roles worth a look.
			</h1>
			<p class="mt-2 max-w-xl text-sm leading-relaxed text-ink-muted">
				{data.total} listings in the workspace. Search by role, company or location.
			</p>
		</div>
		<div class="flex flex-wrap gap-2">
			<a
				href={data.fresh ? '/jobs' : '/jobs?fresh=today'}
				class="inline-flex h-10 items-center rounded-full border px-4 text-sm font-semibold"
				class:border-brand={data.fresh}
				class:bg-brand={data.fresh}
				class:text-on-brand={data.fresh}
				class:border-line-strong={!data.fresh}
				class:bg-surface={!data.fresh}
				class:text-ink={!data.fresh}
			>
				{data.fresh ? 'Showing today' : 'Scraped today'}
			</a>
			<a
				href="/dashboard"
				class="inline-flex h-10 items-center rounded-full border border-line-strong bg-surface px-4 text-sm font-semibold text-ink hover:bg-surface-2"
			>
				Back to matches
			</a>
		</div>
	</div>

	<form method="GET" class="mt-6 grid gap-3 rounded-2xl border border-line bg-surface p-4 sm:grid-cols-[1fr_180px_180px_auto]">
		{#if data.fresh}
			<input type="hidden" name="fresh" value="today" />
		{/if}
		<label class="block text-xs font-semibold uppercase tracking-wider text-ink-muted">
			Search
			<input
				name="q"
				value={data.q}
				placeholder="Role, company, keyword"
				class="mt-1 h-11 w-full rounded-xl border border-line bg-canvas px-3 text-sm font-normal text-ink outline-none focus:border-brand"
			/>
		</label>
		<label class="block text-xs font-semibold uppercase tracking-wider text-ink-muted">
			Category
			<select
				name="category"
				class="mt-1 h-11 w-full rounded-xl border border-line bg-canvas px-3 text-sm font-normal text-ink outline-none focus:border-brand"
			>
				<option value="">All categories</option>
				{#each data.categories as category}
					<option value={category} selected={category === data.category}>{category}</option>
				{/each}
			</select>
		</label>
		<label class="block text-xs font-semibold uppercase tracking-wider text-ink-muted">
			Location
			<input
				name="location"
				value={data.location}
				placeholder="Harare, remote..."
				class="mt-1 h-11 w-full rounded-xl border border-line bg-canvas px-3 text-sm font-normal text-ink outline-none focus:border-brand"
			/>
		</label>
		<button
			type="submit"
			class="mt-5 inline-flex h-11 items-center justify-center rounded-full bg-brand px-5 text-sm font-semibold text-on-brand hover:bg-brand-hover"
		>
			Search
		</button>
	</form>

	{#if data.jobs.length === 0}
		<div class="mt-8 rounded-2xl border border-line bg-surface p-8 text-center">
			<h2 class="font-display text-lg font-bold text-ink">No roles match that search.</h2>
			<p class="mt-2 text-sm text-ink-muted">Try a broader keyword or clear the filters.</p>
			<a href="/jobs" class="mt-4 inline-flex text-sm font-semibold text-link">Clear filters</a>
		</div>
	{:else}
		<div class="mt-6 grid gap-3">
			{#each data.jobs as job}
				<article class="rounded-2xl border border-line bg-surface p-5 transition-colors hover:border-line-strong">
					<div class="flex flex-wrap items-start justify-between gap-4">
						<div class="min-w-0">
							<p class="text-xs font-semibold uppercase tracking-[0.16em] text-ink-muted">
								{job.company}
							</p>
							<h2 class="mt-1 font-display text-xl font-bold leading-tight text-ink">
								<a href={`/jobs/${job.id}`} class="hover:text-link">{job.title}</a>
							</h2>
							<p class="mt-1 text-sm text-ink-muted">
								{job.location}{job.type ? ` - ${job.type}` : ''}{job.remote ? ' - Remote' : ''}
							</p>
						</div>
						{#if job.compensation}
							<span class="rounded-full bg-surface-2 px-3 py-1 text-xs font-semibold text-ink-muted">
								{job.compensation}
							</span>
						{/if}
					</div>
					<p class="mt-3 line-clamp-2 text-sm leading-relaxed text-ink-muted">{job.summary}</p>
					<div class="mt-4 flex flex-wrap items-center justify-between gap-3">
						<p class="text-xs text-ink-muted">
							{job.category ?? 'General'}{job.datePosted ? ` - posted ${job.datePosted}` : ''}{job.addedAt ? ` - added ${new Date(job.addedAt).toLocaleDateString()}` : ''}
						</p>
						<a href={`/jobs/${job.id}`} class="text-sm font-semibold text-link">
							View role
						</a>
					</div>
				</article>
			{/each}
		</div>

		<div class="mt-6 flex items-center justify-between gap-3">
			{#if data.page > 1}
				<a href={pageHref(data.page - 1)} class="text-sm font-semibold text-link">Previous</a>
			{:else}
				<span></span>
			{/if}
			<p class="text-xs text-ink-muted">Page {data.page} of {data.pages}</p>
			{#if data.page < data.pages}
				<a href={pageHref(data.page + 1)} class="text-sm font-semibold text-link">Next</a>
			{:else}
				<span></span>
			{/if}
		</div>
	{/if}
</div>
