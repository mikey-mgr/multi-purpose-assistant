<script lang="ts">
	import CvView from '../../../lib/components/CvView.svelte';
	import { renderMarkdown } from '../../../lib/markdown';
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();

	function label(type: string) {
		if (type === 'resume') return 'CV';
		if (type === 'cover_letter') return 'Cover letter';
		if (type === 'interview_prep') return 'Interview prep';
		return type;
	}

	const cv = $derived.by(() => {
		if (!data.document.rendercvYaml) return null;
		try {
			const parsed = JSON.parse(data.document.rendercvYaml) as { cv?: Record<string, unknown> };
			return parsed.cv ?? null;
		} catch {
			return null;
		}
	});

	const interviewHtml = $derived(
		data.document.type === 'interview_prep' && data.document.content
			? renderMarkdown(data.document.content)
			: ''
	);

	const editable = $derived(data.document.type === 'cover_letter');
	let editing = $state(false);
	let draft = $state('');
	let saving = $state(false);
	let saveNotice = $state('');
	let saveError = $state('');

	function startEditing() {
		draft = data.document.content ?? '';
		saveNotice = '';
		saveError = '';
		editing = true;
	}

	async function save() {
		saving = true;
		saveNotice = '';
		saveError = '';
		const response = await fetch(`/api/documents/${data.document.id}`, {
			method: 'PATCH',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ content: draft })
		});
		const result = (await response.json().catch(() => ({}))) as {
			error?: string;
			rebuild?: { blockers?: string[]; ok?: boolean; error?: string } | null;
		};
		saving = false;
		if (!response.ok) {
			saveError = result.error ?? 'Could not save your changes';
			return;
		}
		if (result.rebuild && result.rebuild.ok === false) {
			saveError = `Saved, but the application kit could not be rebuilt: ${result.rebuild.error ?? 'unknown error'}`;
			return;
		}
		editing = false;
		saveNotice = result.rebuild
			? 'Saved. The application kit was rebuilt with your edits.'
			: 'Saved.';
		location.reload();
	}
</script>

<svelte:head>
	<title>{label(data.document.type)} - {data.document.jobTitle ?? 'Document'} - Mukana</title>
	<meta name="robots" content="noindex" />
</svelte:head>

<div class="mx-auto max-w-3xl px-4 py-8 pb-24 sm:px-6">
	<a href="/documents" class="text-sm font-semibold text-link">Back to documents</a>

	<div class="mt-5">
		<div class="mb-3 flex flex-wrap items-end justify-between gap-2">
			<div>
				<p class="text-xs font-semibold uppercase tracking-[0.18em] text-brand">
					{label(data.document.type)}
				</p>
				<h1 class="mt-1 font-display text-2xl font-bold text-ink">
					{data.document.jobTitle ?? 'Tailored document'}
				</h1>
				<p class="mt-1 text-sm text-ink-muted">{data.document.company ?? 'General'}</p>
			</div>
			<div class="flex flex-wrap items-center gap-3">
				{#if data.document.jobId}
					<a href={`/jobs/${data.document.jobId}`} class="text-sm font-semibold text-link">
						View role
					</a>
				{/if}
				{#if editable && !editing}
					<button
						type="button"
						onclick={startEditing}
						class="inline-flex h-9 items-center rounded-full border border-line-strong bg-surface px-4 text-xs font-semibold text-ink hover:bg-surface-2"
					>
						Edit text
					</button>
				{/if}
				{#if data.document.pdfPath}
					<a
						href={`/api/documents/${data.document.id}/file`}
						class="inline-flex h-9 items-center rounded-full bg-brand px-4 text-xs font-semibold text-on-brand hover:bg-brand-hover"
					>
						Download PDF
					</a>
				{/if}
			</div>
		</div>

		{#if saveNotice}
			<p class="mb-3 rounded-xl bg-match-light px-4 py-3 text-sm text-match-text" role="status">
				{saveNotice}
			</p>
		{/if}
		{#if saveError}
			<p class="mb-3 rounded-xl bg-bad/10 px-4 py-3 text-sm font-medium text-bad" role="alert">
				{saveError}
			</p>
		{/if}

		{#if editing}
			<div class="rounded-2xl border border-line bg-surface p-4 sm:p-6">
				<p class="text-xs font-semibold uppercase tracking-wider text-ink-muted">
					Edit cover letter
				</p>
				<p class="mt-1 text-xs leading-relaxed text-ink-muted">
					Saving rebuilds this application's PDF and merged kit with your changes.
				</p>
				<textarea
					bind:value={draft}
					rows="22"
					maxlength="60000"
					class="mt-3 w-full rounded-xl border border-line bg-canvas px-3 py-3 font-sans text-sm leading-relaxed text-ink outline-none focus:border-brand"
				></textarea>
				<div class="mt-3 flex flex-wrap items-center gap-2">
					<button
						type="button"
						onclick={save}
						disabled={saving}
						class="inline-flex h-10 items-center rounded-full bg-brand px-4 text-sm font-semibold text-on-brand hover:bg-brand-hover disabled:opacity-60"
					>
						{saving ? 'Saving...' : 'Save and rebuild'}
					</button>
					<button
						type="button"
						onclick={() => (editing = false)}
						disabled={saving}
						class="inline-flex h-10 items-center rounded-full border border-line-strong bg-surface px-4 text-sm font-semibold text-ink hover:bg-surface-2 disabled:opacity-60"
					>
						Cancel
					</button>
				</div>
			</div>
		{:else if data.document.type === 'resume' && cv}
			<CvView {cv} />
		{:else if interviewHtml}
			<article class="markdown rounded-2xl border border-line bg-surface p-6 sm:p-8">
				{@html interviewHtml}
			</article>
		{:else if data.document.content}
			<div class="rounded-2xl border border-line bg-surface p-6 sm:p-8">
				<pre class="whitespace-pre-wrap break-words font-sans text-sm leading-relaxed text-ink">{data.document
						.content}</pre>
			</div>
		{:else}
			<div class="rounded-2xl border border-line bg-surface p-6 sm:p-8">
				<p class="text-sm text-ink-muted">This document has no saved text content.</p>
			</div>
		{/if}

		{#if data.document.rendercvYaml}
			<details class="mt-4 rounded-xl border border-line bg-surface-2 p-4">
				<summary class="cursor-pointer text-sm font-semibold text-ink">RenderCV source</summary>
				<pre class="mt-3 max-h-96 overflow-auto whitespace-pre-wrap text-xs text-ink-muted"
					>{data.document.rendercvYaml}</pre
				>
			</details>
		{/if}
	</div>
</div>

<style>
	.markdown :global(h1) {
		margin-top: 1.5rem;
		font-size: 1.5rem;
		font-weight: 700;
		color: var(--color-ink);
	}
	.markdown :global(h2) {
		margin-top: 1.5rem;
		font-size: 1.125rem;
		font-weight: 700;
		color: var(--color-ink);
	}
	.markdown :global(h3) {
		margin-top: 1.25rem;
		font-size: 1rem;
		font-weight: 700;
		color: var(--color-ink);
	}
	.markdown :global(h1:first-child),
	.markdown :global(h2:first-child),
	.markdown :global(h3:first-child) {
		margin-top: 0;
	}
	.markdown :global(p) {
		margin-top: 0.75rem;
		line-height: 1.7;
		color: var(--color-ink);
	}
	.markdown :global(ul),
	.markdown :global(ol) {
		margin-top: 0.75rem;
		padding-left: 1.25rem;
		line-height: 1.7;
		color: var(--color-ink);
	}
	.markdown :global(ul) {
		list-style: disc;
	}
	.markdown :global(ol) {
		list-style: decimal;
	}
	.markdown :global(li) {
		margin-top: 0.3rem;
	}
	.markdown :global(strong) {
		font-weight: 700;
		color: var(--color-ink);
	}
	.markdown :global(a) {
		color: var(--color-link);
		text-decoration: underline;
		text-underline-offset: 2px;
	}
</style>
