<script lang="ts">
	let { compact = false }: { compact?: boolean } = $props();
</script>

<a href="/" class="inline-flex items-center gap-2.5 rounded-lg" aria-label="Mukana home">
	<svg viewBox="0 0 40 40" class="size-9 shrink-0" aria-hidden="true">
		<rect width="40" height="40" rx="11" fill="#C84B26" />
		<path
			d="M10 29V14.5c0-1.4 1.8-2 2.7-1L20 21.5l7.3-8c.9-1 2.7-.4 2.7 1V29"
			fill="none"
			stroke="#FAF7F2"
			stroke-width="4.2"
			stroke-linecap="round"
			stroke-linejoin="round"
		/>
		<circle cx="31" cy="9.5" r="3.6" fill="#1B6B48" />
	</svg>
	{#if !compact}
		<span class="font-display text-lg font-bold tracking-tight text-ink">Mukana</span>
	{/if}
</a>
