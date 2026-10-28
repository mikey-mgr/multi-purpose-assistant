<script lang="ts">
	let { name, class: className = 'size-5' }: { name: string; class?: string } = $props();
</script>

<svg
	viewBox="0 0 24 24"
	class={className}
	fill="none"
	stroke="currentColor"
	stroke-width="1.7"
	stroke-linecap="round"
	stroke-linejoin="round"
	aria-hidden="true"
>
	{#if name === 'target'}
		<circle cx="12" cy="12" r="8"></circle>
		<circle cx="12" cy="12" r="3"></circle>
		<path d="M12 2v3M22 12h-3M12 22v-3M2 12h3"></path>
	{:else if name === 'file'}
		<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"></path>
		<path d="M14 3v5h5M9 13h6M9 17h6"></path>
	{:else if name === 'send'}
		<path d="m21 3-7 18-3.5-7.5L3 10z"></path>
		<path d="M10.5 13.5 21 3"></path>
	{:else if name === 'mic'}
		<rect x="9" y="3" width="6" height="11" rx="3"></rect>
		<path d="M5 11a7 7 0 0 0 14 0M12 18v3"></path>
	{:else if name === 'chart'}
		<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"></path>
	{:else if name === 'key'}
		<circle cx="8" cy="15" r="4"></circle>
		<path d="m11 12 8-8M16 4l3 3M14 6l3 3"></path>
	{:else if name === 'check'}
		<path d="m4 12 5 5L20 6"></path>
	{:else if name === 'arrow'}
		<path d="M4 12h16M14 6l6 6-6 6"></path>
	{:else if name === 'briefcase'}
		<rect x="3" y="7" width="18" height="13" rx="2"></rect>
		<path d="M9 7V5a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v2M3 12h18"></path>
	{:else if name === 'spark'}
		<path d="M12 3v4M12 17v4M3 12h4M17 12h4M5.6 5.6l2.8 2.8M15.6 15.6l2.8 2.8M18.4 5.6l-2.8 2.8M8.4 15.6l-2.8 2.8"></path>
	{:else if name === 'user'}
		<circle cx="12" cy="8" r="4"></circle>
		<path d="M4 21a8 8 0 0 1 16 0"></path>
	{:else if name === 'eye'}
		<path d="M2 12s3.5-6 10-6 10 6 10 6-3.5 6-10 6S2 12 2 12Z"></path>
		<circle cx="12" cy="12" r="3"></circle>
	{:else if name === 'eye-off'}
		<path d="m3 3 18 18"></path>
		<path d="M10.6 6.2A10.8 10.8 0 0 1 12 6c6.5 0 10 6 10 6a17.6 17.6 0 0 1-2.2 3"></path>
		<path d="M6.5 6.5A17.4 17.4 0 0 0 2 12s3.5 6 10 6a10.7 10.7 0 0 0 4.3-.9"></path>
		<path d="M9.9 9.9a3 3 0 0 0 4.2 4.2"></path>
	{/if}
</svg>
