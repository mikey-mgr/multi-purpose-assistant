	<script lang="ts">
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();

	function sizeLabel(bytes: number) {
		if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
		return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
	}

	function dateLabel(value: Date | string) {
		return new Date(value).toLocaleDateString('en-GB', {
			day: 'numeric',
			month: 'short',
			year: 'numeric'
		});
	}
</script>

<svelte:head>
	<title>Application kits - Mukana</title>
	<meta
		name="description"
		content="Download your tailored CV, cover letter and merged application kits."
	/>
</svelte:head>

<div class="mx-auto max-w-4xl px-4 py-8 pb-24 sm:px-6">
	<div class="flex flex-wrap items-end justify-between gap-4">
		<div>
			<p class="text-xs font-semibold uppercase tracking-[0.18em] text-brand">Application kits</p>
			<h1 class="mt-2 text-3xl font-bold tracking-tight text-ink sm:text-4xl">
				Everything you need to apply.
			</h1>
			<p class="mt-2 max-w-xl text-sm leading-relaxed text-ink-muted">
				Each kit contains the tailored CV, cover letter, and any extra documents the employer
				asked for. Download the PDF or the ready-to-send .eml file.
			</p>
		</div>
		<a
			href="/dashboard"
			class="inline-flex h-10 items-center rounded-full border border-line-strong bg-surface px-4 text-sm font-semibold text-ink hover:bg-surface-2"
		>
			Back to dashboard
		</a>
	</div>

	{#if data.kits.length === 0}
		<div class="mt-8 rounded-2xl border border-line bg-surface p-8 text-center">
			<h2 class="font-display text-lg font-bold text-ink">No kits yet.</h2>
			<p class="mt-2 text-sm text-ink-muted">
				A kit appears after a match is generated. Run matching or wait for the next scheduled pass.
			</p>
			<a href="/matches" class="mt-4 inline-flex text-sm font-semibold text-link">View matches</a>
		</div>
	{:else}
		<div class="mt-6 space-y-4">
			{#each data.kits as kit}
				<article class="rounded-2xl border border-line bg-surface p-5">
					<div class="flex flex-wrap items-start justify-between gap-3">
						<div class="min-w-0">
							<p class="text-xs font-semibold uppercase tracking-[0.16em] text-ink-muted">
								{kit.company}
							</p>
							<h2 class="mt-1 font-display text-lg font-bold leading-tight text-ink">
								{kit.jobTitle}
							</h2>
							<p class="mt-1 text-xs text-ink-muted">
								{kit.recipient} · {dateLabel(kit.createdAt)}
							</p>
						</div>
						<div class="flex shrink-0 flex-wrap items-center gap-2">
							<span class="rounded-full bg-surface-2 px-2.5 py-1 text-xs font-semibold text-ink">
								{kit.attachments.length} attachment{kit.attachments.length === 1 ? '' : 's'}
							</span>
							{#if kit.merged}
								<span class="rounded-full bg-match-light px-2.5 py-1 text-xs font-bold text-match-text">
									Single PDF
								</span>
							{/if}
						</div>
					</div>

					<p class="mt-3 text-sm leading-relaxed text-ink-muted">
						Subject: <span class="font-medium text-ink">{kit.subject}</span>
					</p>

					{#if kit.blockers.length}
						<div class="mt-3 rounded-xl border border-warn/30 bg-warn/10 px-3 py-2">
							<p class="text-xs font-semibold uppercase tracking-wider text-warn">
								Needs review
							</p>
							<ul class="mt-1 space-y-1 text-xs text-ink">
								{#each kit.blockers as blocker}
									<li>{blocker}</li>
								{/each}
							</ul>
						</div>
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
						{#if kit.jobId}
							<a
								href={`/jobs/${kit.jobId}`}
								class="inline-flex h-9 items-center rounded-full border border-line-strong bg-surface px-4 text-xs font-semibold text-ink hover:bg-surface-2"
							>
								View role
							</a>
						{/if}
					</div>

					<p class="mt-3 text-xs text-ink-muted">
						{kit.attachments.map((attachment) => `${attachment.name} (${sizeLabel(attachment.bytes)})`).join(' · ')}
					</p>
				</article>
			{/each}
		</div>
	{/if}
</div>
