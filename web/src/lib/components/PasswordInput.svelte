<script lang="ts">
	import type { FullAutoFill } from 'svelte/elements';
	import Icon from './Icon.svelte';

	let {
		value = $bindable(''),
		id = 'password',
		name = 'password',
		autocomplete = 'current-password',
		required = true,
		minlength = 8,
		maxlength = 128,
		placeholder = ''
	}: {
		value?: string;
		id?: string;
		name?: string;
		autocomplete?: FullAutoFill;
		required?: boolean;
		minlength?: number;
		maxlength?: number;
		placeholder?: string;
	} = $props();

	let visible = $state(false);
</script>

<div class="relative mt-1">
	<input
		{id}
		{name}
		{autocomplete}
		{required}
		{minlength}
		{maxlength}
		{placeholder}
		type={visible ? 'text' : 'password'}
		bind:value
		class="h-12 w-full rounded-xl border border-line bg-canvas px-3 pr-12 text-sm text-ink outline-none transition-colors focus:border-brand"
	/>
	<button
		type="button"
		onclick={() => (visible = !visible)}
		aria-label={visible ? 'Hide password' : 'Show password'}
		aria-pressed={visible}
		class="absolute right-1 top-1 grid size-10 place-items-center rounded-lg text-ink-muted transition-colors hover:bg-surface-2 hover:text-ink"
	>
		<Icon name={visible ? 'eye-off' : 'eye'} class="size-5" />
	</button>
</div>
