---
title: Job Types & Experience
---

```js
const rawJobs = await FileAttachment("data/jobs.csv").csv();
const jobs = rawJobs.map(d => ({...d, remote_eligible: d.remote_eligible || ""}));
const jobTypes = await FileAttachment("data/job_types.csv").csv();
const experience = await FileAttachment("data/experience.csv").csv();
```

# Job Types & Experience Levels

<div class="card-full">

### Employment Types

```js
display(Plot.plot({
  height: 300,
  marginLeft: 100,
  y: {label: null, domain: jobTypes.map(d => d.type).reverse()},
  x: {label: "Jobs"},
  color: {scheme: "Pastel1"},
  marks: [
    Plot.barX(jobTypes, {x: "job_count", y: "type", fill: "type", tip: true}),
    Plot.text(jobTypes, {x: "job_count", y: "type", text: d => d.job_count, dx: 3, textAnchor: "start", fill: "white"})
  ]
}))
```

</div>

## Experience Level Requirements

```js
display(Plot.plot({
  marginLeft: 250,
  marginRight: 40,
  height: 400,
  y: {label: null, domain: experience.slice(0, 20).map(d => d.level).reverse()},
  x: {label: "Jobs"},
  marks: [
    Plot.barX(experience.slice(0, 20), {x: "job_count", y: "level", fill: "#f28e2b", tip: true}),
    Plot.text(experience.slice(0, 20), {x: "job_count", y: "level", text: d => d.job_count, dx: 3, textAnchor: "start", fill: "white"})
  ]
}))
```

## Job Type Distribution by Category

```js
// Cross-tabulation
const crossTab = d3.rollup(
  jobs.filter(d => d.category && d.job_type),
  v => v.length,
  d => d.category,
  d => d.job_type
);
const heatmapData = [];
for (const [cat, types] of crossTab) {
  for (const [type, count] of types) {
    heatmapData.push({category: cat, job_type: type, count});
  }
}

display(Plot.plot({
  marginLeft: 120,
  marginBottom: 100,
  height: 400,
  x: {label: null, tickRotate: -30},
  y: {label: null},
  color: {scheme: "Blues", label: "Jobs"},
  marks: [
    Plot.rect(heatmapData, {x: "job_type", y: "category", fill: "count", tip: true}),
    Plot.text(heatmapData, {x: "job_type", y: "category", text: d => d.count > 0 ? d.count : "", fill: "black"})
  ]
}))
```

```js
const style = html`<style>
  .grid { display: grid; gap: 1rem; }
  .card { padding: 1rem; border: 1px solid #ddd; border-radius: 8px; background: var(--theme-background-secondary); }
  .card-full { padding: 1rem; border: 1px solid #ddd; border-radius: 8px; background: var(--theme-background-secondary); margin-bottom: 1rem; }
  @media (max-width: 768px) { .grid-cols-3 { grid-template-columns: 1fr; } }
</style>`;
document.head.appendChild(style);
```
