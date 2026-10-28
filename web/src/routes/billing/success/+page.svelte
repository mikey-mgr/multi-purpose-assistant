<svelte:head>
	<title>Payment received - Mukana</title>
	<meta name="robots" content="noindex" />
</svelte:head>

<div class="mx-auto flex min-h-[calc(100dvh-8rem)] max-w-md flex-col justify-center px-4 py-12">
	<div class="rounded-2xl border border-line bg-surface p-6 text-center shadow-sm">
		<p class="text-xs font-semibold uppercase tracking-[0.18em] text-match-text">Payment received</p>
		<h1 class="mt-2 font-display text-2xl font-bold text-ink">Your plan is active.</h1>
		<p class="mt-2 text-sm leading-relaxed text-ink-muted">
			Paynow will confirm the transaction. You can return to your workspace and keep applying.
		</p>
		<a
			href="/dashboard"
			class="mt-6 inline-flex h-11 items-center justify-center rounded-full bg-brand px-5 text-sm font-semibold text-on-brand hover:bg-brand-hover"
		>
			Back to dashboard
		</a>
	</div>
</div>
