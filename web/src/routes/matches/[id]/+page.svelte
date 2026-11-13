<script lang="ts">
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();

	let busy = $state<'revalidate' | 'force' | null>(null);
	let notice = $state('');
	let errorMessage = $state('');

	const kit = $derived(data.kit);
	const needsReview = $derived((kit?.blockers.length ?? 0) > 0);
	const applied = $derived(data.match.status === 'applied');

	function sizeLabel(bytes: number) {
		if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
		return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
	}

	async function revalidate() {
		busy = 'revalidate';
		notice = '';
		errorMessage = '';
		const response = await fetch(`/api/matches/${data.match.id}/revalidate`, { method: 'POST' });
		const result = (await response.json().catch(() => ({}))) as {
			error?: string;
			blockers?: string[];
		};
		busy = null;
		if (!response.ok) {
			errorMessage = result.error ?? 'Could not re-check this application';
			return;
		}
		notice =
			(result.blockers?.length ?? 0) === 0
				? 'All requirements are now satisfied. The kit has been rebuilt.'
				: 'Re-checked. Some requirements are still outstanding.';
		location.reload();
	}

	async function applyAnyway() {
		if (!confirm('Send this application even though items are flagged for review?')) return;
		busy = 'force';
		notice = '';
		errorMessage = '';
		const response = await fetch(`/api/matches/${data.match.id}/apply-anyway`, {
			method: 'POST'
		});
		const result = (await response.json().catch(() => ({}))) as { error?: string; message?: string };
		busy = null;
		if (!response.ok) {
			errorMessage = result.error ?? 'Could not queue this application';
			return;
		}
		notice = result.message ?? 'Queued for sending.';
	}
</script>

<svelte:head>
	<title>{data.job.title} - Mukana</title>
	<meta name="robots" content="noindex" />
</svelte:head>

<div class="mx-auto max-w-3xl px-4 py-8 pb-24 sm:px-6">
	<div class="flex flex-wrap items-center justify-between gap-3">
		<a href="/matches" class="text-sm font-semibold text-link">Back to matches</a>
		<div class="flex items-center gap-3">
			<span class="rounded-full bg-surface-2 px-2.5 py-1 text-xs font-bold text-ink">
				{data.match.status}
			</span>
			{#if data.match.score !== null}
				<span class="rounded-full bg-match-light px-2.5 py-1 text-xs font-bold text-match-text">
					{data.match.score}% fit
				</span>
			{/if}
		</div>
	</div>

	<div class="mt-5">
		<p class="text-xs font-semibold uppercase tracking-[0.16em] text-ink-muted">
			{data.job.company}
		</p>
		<h1 class="mt-1 font-display text-2xl font-bold text-ink sm:text-3xl">{data.job.title}</h1>
		<p class="mt-1 text-sm text-ink-muted">
			{[data.job.location, data.job.type, data.job.compensation].filter(Boolean).join(' · ')}
		</p>
	</div>

	{#if notice}
		<p class="mt-4 rounded-xl bg-match-light px-4 py-3 text-sm text-match-text" role="status">
			{notice}
		</p>
	{/if}
	{#if errorMessage}
		<p class="mt-4 rounded-xl bg-bad/10 px-4 py-3 text-sm font-medium text-bad" role="alert">
			{errorMessage}
		</p>
	{/if}

	{#if data.match.reason}
		<section class="mt-6 rounded-2xl border border-line bg-surface p-5">
			<h2 class="font-display text-lg font-bold text-ink">Why this matched</h2>
			<p class="mt-2 whitespace-pre-line text-sm leading-relaxed text-ink-muted">
				{data.match.reason}
			</p>
		</section>
	{/if}

	<section class="mt-4 rounded-2xl border border-line bg-surface p-5">
		<div class="flex flex-wrap items-center justify-between gap-2">
			<h2 class="font-display text-lg font-bold text-ink">Application</h2>
			{#if kit}
				<p class="text-xs text-ink-muted">{kit.recipient}</p>
			{/if}
		</div>

		{#if !kit}
			<div class="mt-3 rounded-xl border border-line bg-surface-2 px-4 py-3 text-sm text-ink-muted">
				No application kit yet. Run matching or wait for the next generation pass.
			</div>
		{:else}
			<p class="mt-3 text-sm text-ink-muted">
				Subject: <span class="font-medium text-ink">{kit.subject}</span>
			</p>

			{#if needsReview}
				<div class="mt-3 rounded-xl border border-warn/30 bg-warn/10 px-4 py-3">
					<p class="text-xs font-semibold uppercase tracking-wider text-warn">Needs review</p>
					<ul class="mt-2 space-y-1 text-sm text-ink">
						{#each kit.blockers as blocker}
							<li>· {blocker}</li>
						{/each}
					</ul>
				</div>
			{:else}
				<div class="mt-3 rounded-xl border border-match/30 bg-match-light px-4 py-3">
					<p class="text-sm font-semibold text-match-text">Ready to send</p>
					<p class="mt-1 text-xs text-ink-muted">
						Every requirement the employer listed is attached.
					</p>
				</div>
			{/if}

			{#if data.match.missing.length}
				<div class="mt-3 rounded-xl border border-line bg-surface-2 px-4 py-3">
					<p class="text-xs font-semibold uppercase tracking-wider text-ink-muted">
						Documents still missing
					</p>
					<ul class="mt-1 space-y-1 text-sm text-ink">
						{#each data.match.missing as item}
							<li>{item.label}</li>
						{/each}
					</ul>
					<a
						href="/documents"
						class="mt-2 inline-flex text-sm font-semibold text-link hover:underline"
					>
						Upload the missing documents
					</a>
				</div>
			{/if}

			{#if kit.notes}
				<p class="mt-3 text-xs leading-relaxed text-ink-muted">{kit.notes}</p>
			{/if}

			<div class="mt-4 flex flex-wrap gap-2">
				{#each kit.attachments as attachment}
					<a
						href={`/api/applications/${kit.id}/file?index=${attachment.index}`}
						title={attachment.name}
						class="inline-flex h-9 items-center rounded-full bg-brand px-4 text-xs font-semibold text-on-brand hover:bg-brand-hover"
					>
						Download {attachment.mime === 'application/pdf'
							? 'PDF'
							: attachment.mime.includes('wordprocessingml')
								? 'DOCX'
								: 'file'}
					</a>
				{/each}
				<a
					href={`/api/applications/${kit.id}/kit.eml`}
					class="inline-flex h-9 items-center rounded-full border border-line-strong bg-surface px-4 text-xs font-semibold text-ink hover:bg-surface-2"
				>
					Download .eml
				</a>
			</div>
			<p class="mt-2 text-xs text-ink-muted">
				{kit.attachments
					.map((attachment) => `${attachment.name} (${sizeLabel(attachment.bytes)})`)
					.join(' · ')}
			</p>

			{#if applied}
				<p class="mt-4 rounded-xl bg-surface-2 px-4 py-3 text-sm text-ink-muted">
					This application has already been sent.
				</p>
			{:else}
				<div class="mt-5 flex flex-wrap gap-2 border-t border-line pt-4">
					<button
						type="button"
						onclick={revalidate}
						disabled={busy !== null}
						class="inline-flex h-10 items-center rounded-full border border-line-strong bg-surface px-4 text-sm font-semibold text-ink hover:bg-surface-2 disabled:opacity-60"
					>
						{busy === 'revalidate' ? 'Re-checking...' : 'Re-check requirements'}
					</button>
					{#if needsReview && data.canForceApply}
						<button
							type="button"
							onclick={applyAnyway}
							disabled={busy !== null}
							class="inline-flex h-10 items-center rounded-full bg-brand px-4 text-sm font-semibold text-on-brand hover:bg-brand-hover disabled:opacity-60"
						>
							{busy === 'force' ? 'Queueing...' : 'Apply anyway'}
						</button>
					{/if}
				</div>
				<p class="mt-2 text-xs leading-relaxed text-ink-muted">
					Re-check after uploading documents or completing your profile. Apply anyway sends
					the kit as it stands, even with items flagged above.
				</p>
			{/if}
		{/if}
	</section>

	{#if data.documents.length}
		<section class="mt-4 rounded-2xl border border-line bg-surface p-5">
			<h2 class="font-display text-lg font-bold text-ink">Generated documents</h2>
			<p class="mt-1 text-sm text-ink-muted">Open to review or edit the cover letter.</p>
			<div class="mt-3 space-y-2">
				{#each data.documents as document}
					<a
						href={`/documents/${document.id}`}
						class="flex items-center justify-between rounded-xl border border-line bg-surface-2 px-4 py-3 text-sm font-semibold text-ink hover:border-line-strong"
					>
						<span>
							{document.type === 'resume'
								? 'CV'
								: document.type === 'cover_letter'
									? 'Cover letter'
									: document.type}
						</span>
						<span class="text-xs font-semibold text-link">
							{document.type === 'cover_letter' ? 'Edit' : 'Open'}
						</span>
					</a>
				{/each}
			</div>
		</section>
	{/if}
</div>
