<script lang="ts">
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();

	function label(type: string) {
		if (type === 'resume') return 'CV';
		if (type === 'cover_letter') return 'Cover letter';
		if (type === 'interview_prep') return 'Interview prep';
		return type;
	}
</script>

<svelte:head>
	<title>{label(data.document.type)} - {data.document.jobTitle ?? 'Document'} - Mukana</title>
	<meta name="robots" content="noindex" />
</svelte:head>

<div class="mx-auto max-w-3xl px-4 py-8 pb-24 sm:px-6">
	<a href="/documents" class="text-sm font-semibold text-link">Back to documents</a>

	<div class="mt-5 rounded-2xl border border-line bg-surface p-6 sm:p-8">
		<p class="text-xs font-semibold uppercase tracking-[0.18em] text-brand">
			{label(data.document.type)}
		</p>
		<h1 class="mt-2 font-display text-2xl font-bold text-ink">
			{data.document.jobTitle ?? 'Tailored document'}
		</h1>
		<p class="mt-1 text-sm text-ink-muted">
			{data.document.company ?? 'General'}{data.document.model ? ` - ${data.document.model}` : ''}
		</p>

		{#if data.document.jobId}
			<a href={`/jobs/${data.document.jobId}`} class="mt-3 inline-flex text-sm font-semibold text-link">
				View the role
			</a>
		{/if}

		{#if data.document.content}
			<pre class="mt-6 whitespace-pre-wrap break-words text-sm leading-relaxed text-ink">{data.document
					.content}</pre>
		{:else}
			<p class="mt-6 text-sm text-ink-muted">This document has no saved text content.</p>
		{/if}

		{#if data.document.rendercvYaml}
			<details class="mt-8 rounded-xl border border-line bg-surface-2 p-4">
				<summary class="cursor-pointer text-sm font-semibold text-ink">RenderCV source</summary>
				<pre class="mt-3 max-h-96 overflow-auto whitespace-pre-wrap text-xs text-ink-muted"
					>{data.document.rendercvYaml}</pre
				>
			</details>
		{/if}
	</div>
</div>
