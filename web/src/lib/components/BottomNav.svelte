<script lang="ts">
	import Icon from './Icon.svelte';

	const items = [
		{ href: '/dashboard', label: 'Jobs', icon: 'briefcase' },
		{ href: '/dashboard#matches', label: 'Matches', icon: 'target' },
		{ href: '/dashboard#documents', label: 'Docs', icon: 'file' },
		{ href: '/dashboard#prep', label: 'Prep', icon: 'mic' },
		{ href: '/dashboard#profile', label: 'Profile', icon: 'user' }
	];
</script>

<nav
	class="fixed inset-x-0 bottom-0 z-40 border-t border-line bg-surface/95 backdrop-blur md:hidden"
	aria-label="Primary"
>
	<div class="mx-auto grid max-w-md grid-cols-5">
		{#each items as item}
			<a
				href={item.href}
				class="flex min-h-14 flex-col items-center justify-center gap-1 text-[11px] font-medium text-ink-muted hover:text-ink"
			>
				<Icon name={item.icon} class="size-5" />
				<span>{item.label}</span>
			</a>
		{/each}
	</div>
</nav>


