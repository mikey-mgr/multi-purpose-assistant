<script lang="ts">
	import { onMount } from 'svelte';
	import type { MatchJob } from '../types';

	let { job, class: className = '' }: { job: MatchJob; class?: string } = $props();

	let card: HTMLElement | undefined = $state();
	let revealed = $state(false);
	let lite = $state(false);
	let reduced = $state(false);
	let frame = 0;
	let pointerX = 0;
	let pointerY = 0;
	let touchStart: { x: number; y: number; at: number } | null = null;

	const titleId = $derived(`job-${job.id}-title`);

	function apply() {
		frame = 0;
		if (!card) return;
		const rect = card.getBoundingClientRect();
		card.style.setProperty('--sx', `${pointerX - rect.left}px`);
		card.style.setProperty('--sy', `${pointerY - rect.top}px`);
	}

	function track(x: number, y: number) {
		pointerX = x;
		pointerY = y;
		if (!frame) frame = requestAnimationFrame(apply);
	}

	function radius(value: number) {
		card?.style.setProperty('--sr', `${value}px`);
	}

	function enter(event: PointerEvent) {
		if (lite || event.pointerType !== 'mouse') return;
		track(event.clientX, event.clientY);
		radius(160);
	}

	function move(event: PointerEvent) {
		if (lite || event.pointerType !== 'mouse') return;
		track(event.clientX, event.clientY);
	}

	function leave() {
		if (!revealed) radius(0);
	}

	function down(event: PointerEvent) {
		if (event.pointerType === 'mouse') return;
		touchStart = { x: event.clientX, y: event.clientY, at: Date.now() };
	}

	function up(event: PointerEvent) {
		if (event.pointerType === 'mouse') return;
		if (!touchStart) return;

		const moved = Math.abs(event.clientX - touchStart.x);
		const drifted = Math.abs(event.clientY - touchStart.y);
		const elapsed = Date.now() - touchStart.at;
		touchStart = null;

		if (moved < 10 && drifted < 10 && elapsed < 500) {
			revealed = !revealed;
			radius(revealed ? 2000 : 0);
		}
	}

	function cancel() {
		touchStart = null;
	}

	function toggle() {
		revealed = !revealed;
		radius(revealed ? 2000 : 0);
	}

	onMount(() => {
		const motion = window.matchMedia('(prefers-reduced-motion: reduce)');
		reduced = motion.matches;
		const connection = (
			navigator as Navigator & {
				connection?: { saveData?: boolean; effectiveType?: string };
			}
		).connection;
		lite = Boolean(connection?.saveData || /(^|-)2g/.test(connection?.effectiveType ?? ''));
		const onChange = () => (reduced = motion.matches);
		motion.addEventListener('change', onChange);
		return () => {
			motion.removeEventListener('change', onChange);
			if (frame) cancelAnimationFrame(frame);
		};
	});
</script>

<article
	bind:this={card}
	class={`spotlight-card ${className}`}
	class:is-revealed={revealed}
	class:is-lite={lite}
	class:is-reduced={reduced}
	aria-labelledby={titleId}
	onpointerenter={enter}
	onpointermove={move}
	onpointerleave={leave}
	onpointerdown={down}
	onpointerup={up}
	onpointercancel={cancel}
>
	<div class="spotlight-body">
		<div class="spotlight-layer spotlight-base" aria-hidden="true">
			<div class="flex items-start justify-between gap-4">
				<div class="min-w-0">
					<p class="truncate text-xs font-semibold uppercase tracking-[0.18em] text-ink-muted">
						{job.company}
					</p>
					<h3 class="mt-1 line-clamp-2 text-xl font-bold leading-tight text-ink">
						{job.title}
					</h3>
					<p class="mt-1 text-sm text-ink-muted">
						{job.location}{job.type ? ` - ${job.type}` : ''}
					</p>
				</div>
				<span
					class="shrink-0 rounded-full border border-line bg-surface-2 px-3 py-1 text-sm font-semibold text-ink-muted"
				>
					{job.score}%
				</span>
			</div>

			{#if job.salary}
				<p class="mt-4 text-sm font-medium text-ink-muted">{job.salary}</p>
			{/if}

			<div class="mt-5 rounded-xl border border-line bg-surface-2 p-4">
				<p class="text-xs font-semibold uppercase tracking-[0.16em] text-ink-muted">
					Match details hidden
				</p>
				<p class="mt-2 text-sm text-ink-muted">
					Tap or hover to reveal why this role fits your profile.
				</p>
				<div class="mt-4 space-y-2" aria-hidden="true">
					<div class="h-2 w-3/4 rounded-full bg-line"></div>
					<div class="h-2 w-5/6 rounded-full bg-line"></div>
					<div class="h-2 w-2/3 rounded-full bg-line"></div>
				</div>
			</div>
		</div>

		<div class="spotlight-layer spotlight-reveal" aria-hidden="true">
			<div class="flex items-start justify-between gap-4">
				<div class="min-w-0">
					<p class="truncate text-xs font-semibold uppercase tracking-[0.18em] text-match-text">
						{job.company}
					</p>
					<h3 class="mt-1 line-clamp-2 text-xl font-bold leading-tight text-ink">
						{job.title}
					</h3>
					<p class="mt-1 text-sm text-ink-muted">
						{job.location}{job.type ? ` - ${job.type}` : ''}
					</p>
				</div>
				<span
					class="shrink-0 rounded-full bg-match-light px-3 py-1 text-sm font-bold text-match-text"
				>
					{job.score}% fit
				</span>
			</div>

			<p class="mt-4 line-clamp-3 text-sm leading-relaxed text-ink">{job.summary}</p>

			<ul class="mt-4 space-y-2">
				{#each job.reasons as reason}
					<li class="flex gap-2 text-sm leading-snug text-ink">
						<span class="mt-0.5 shrink-0 font-bold text-match-text" aria-hidden="true">+</span>
						<span>{reason}</span>
					</li>
				{/each}
			</ul>

			<div class="mt-4 flex flex-wrap gap-2">
				{#each job.skills as skill}
					<span class="rounded-full bg-match-light px-2.5 py-1 text-xs font-semibold text-match-text">
						{skill}
					</span>
				{/each}
			</div>

			{#if job.gaps.length}
				<div class="mt-4 rounded-xl border border-line bg-surface px-3 py-2.5">
					<p class="text-xs font-semibold uppercase tracking-[0.14em] text-warn">Gaps to bridge</p>
					<p class="mt-1 text-sm leading-snug text-ink-muted">{job.gaps.join(' - ')}</p>
				</div>
			{/if}
		</div>
	</div>

	<div class="spotlight-actions">
		<button
			type="button"
			onclick={toggle}
			onpointerdown={(event) => event.stopPropagation()}
			onpointerup={(event) => event.stopPropagation()}
			aria-expanded={revealed}
			class="inline-flex h-11 items-center justify-center rounded-full bg-brand px-5 text-sm font-semibold text-on-brand transition-colors hover:bg-brand-hover"
		>
			{revealed ? 'Hide match details' : 'Reveal match'}
		</button>
		<a
			href={job.href ?? '/dashboard'}
			onpointerdown={(event) => event.stopPropagation()}
			onpointerup={(event) => event.stopPropagation()}
			class="text-sm font-semibold text-link underline-offset-4 hover:underline"
		>
			View role
		</a>
	</div>

	<div class="sr-only">
		<h3 id={titleId}>{job.title}</h3>
		<p>{job.company} - {job.location}</p>
		<p>Match score {job.score} percent.</p>
		<p>{job.summary}</p>
		<ul>
			{#each job.reasons as reason}
				<li>{reason}</li>
			{/each}
		</ul>
		<p>Skills: {job.skills.join(', ')}.</p>
		{#if job.gaps.length}
			<p>Gaps to bridge: {job.gaps.join(', ')}.</p>
		{/if}
	</div>
</article>

<style>
	.spotlight-card {
		position: relative;
		border: 1px solid var(--color-border);
		border-radius: var(--radius-lg);
		background-color: var(--color-card);
		padding: 20px;
		overflow: hidden;
		touch-action: pan-y;
		-webkit-tap-highlight-color: transparent;
		transition:
			border-color 180ms ease,
			box-shadow 180ms ease;
	}

	.spotlight-card::before {
		content: '';
		position: absolute;
		inset: 0;
		pointer-events: none;
		background:
			radial-gradient(circle at 15% 0%, rgba(200, 75, 38, 0.06), transparent 42%),
			radial-gradient(circle at 85% 100%, rgba(27, 107, 72, 0.05), transparent 45%);
	}

	:global(.dark) .spotlight-card::before {
		background:
			radial-gradient(circle at 15% 0%, rgba(224, 90, 50, 0.12), transparent 42%),
			radial-gradient(circle at 85% 100%, rgba(40, 155, 105, 0.1), transparent 45%);
	}

	.spotlight-card.is-revealed {
		border-color: var(--color-primary);
		box-shadow: var(--shadow-md);
	}

	.spotlight-body {
		position: relative;
		min-height: 18rem;
	}

	.spotlight-layer {
		position: absolute;
		inset: 0;
	}

	.spotlight-base {
		position: relative;
		inset: auto;
		background-color: var(--color-card);
	}

	.spotlight-reveal {
		background-color: var(--color-card);
		clip-path: circle(var(--sr, 0px) at var(--sx, 50%) var(--sy, 50%));
		will-change: clip-path;
	}

	.spotlight-card.is-revealed .spotlight-body {
		min-height: 0;
	}

	.spotlight-card.is-revealed .spotlight-base {
		display: none;
	}

	.spotlight-card.is-revealed .spotlight-reveal {
		position: relative;
		inset: auto;
		clip-path: none;
		will-change: auto;
	}

	.spotlight-reveal::after {
		content: '';
		position: absolute;
		inset: 0;
		pointer-events: none;
		background: radial-gradient(
			circle 180px at var(--sx, 50%) var(--sy, 50%),
			rgba(200, 75, 38, 0.08),
			transparent 70%
		);
	}

	:global(.dark) .spotlight-reveal::after {
		background: radial-gradient(
			circle 180px at var(--sx, 50%) var(--sy, 50%),
			rgba(224, 90, 50, 0.14),
			transparent 70%
		);
	}

	.spotlight-actions {
		position: relative;
		z-index: 2;
		margin-top: 16px;
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 12px;
	}

	.spotlight-card.is-lite .spotlight-reveal,
	.spotlight-card.is-reduced .spotlight-reveal {
		transition: none;
	}

	@media (prefers-reduced-motion: reduce) {
		.spotlight-reveal {
			transition: none;
		}
	}
</style>
