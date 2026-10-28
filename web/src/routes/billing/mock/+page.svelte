<script lang="ts">
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();

	const amount = $derived((data.amountCents / 100).toFixed(2));
</script>

<svelte:head>
	<title>Mock checkout - Mukana</title>
	<meta name="robots" content="noindex" />
</svelte:head>

<div class="mx-auto flex min-h-[calc(100dvh-8rem)] max-w-md flex-col justify-center px-4 py-12">
	<div class="rounded-2xl border border-line bg-surface p-6 shadow-sm">
		<p class="text-xs font-semibold uppercase tracking-[0.18em] text-brand">Mock checkout</p>
		<h1 class="mt-2 font-display text-2xl font-bold text-ink">
			{data.plan.toUpperCase()} - {data.currency} {amount}
		</h1>
		<p class="mt-2 text-sm text-ink-muted">
			This page only appears when <code>PAYNOW_MODE=mock</code>. In production, Paynow hosts this
			step.
		</p>
		<form method="POST" class="mt-6">
			<button
				type="submit"
				class="inline-flex h-12 w-full items-center justify-center rounded-full bg-brand px-5 text-sm font-semibold text-on-brand hover:bg-brand-hover"
			>
				Simulate successful payment
			</button>
		</form>
		<p class="mt-4 text-xs text-ink-muted">Reference: {data.reference}</p>
	</div>
</div>
