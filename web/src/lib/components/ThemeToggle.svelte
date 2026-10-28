<script lang="ts">
	import { onMount } from 'svelte';

	let dark = $state(false);

	onMount(() => {
		dark = document.documentElement.classList.contains('dark');
	});

	function toggle() {
		dark = !dark;
		document.documentElement.classList.toggle('dark', dark);
		try {
			localStorage.setItem('mukana-theme', dark ? 'dark' : 'light');
		} catch {
			/* no-op */
		}
	}
</script>

<button
	type="button"
	onclick={toggle}
	aria-label={dark ? 'Switch to light theme' : 'Switch to dark theme'}
	aria-pressed={dark}
	class="grid size-11 place-items-center rounded-full border border-line bg-surface text-ink transition-colors hover:border-line-strong hover:bg-surface-2"
>
	{#if dark}
		<svg viewBox="0 0 24 24" class="size-5" fill="none" stroke="currentColor" stroke-width="1.8">
			<circle cx="12" cy="12" r="4"></circle>
			<path
				d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"
				stroke-linecap="round"
			></path>
		</svg>
	{:else}
		<svg viewBox="0 0 24 24" class="size-5" fill="none" stroke="currentColor" stroke-width="1.8">
			<path
				d="M20 14.5A8.5 8.5 0 1 1 9.5 4a7 7 0 0 0 10.5 10.5Z"
				stroke-linejoin="round"
			></path>
		</svg>
	{/if}
</button>
