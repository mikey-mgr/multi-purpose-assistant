---
title: Salary & Compensation
---

```js
const rawJobs = await FileAttachment("data/jobs.csv").csv();
const jobs = rawJobs.map(d => ({...d, min_salary: +d.min_salary || 0, max_salary: +d.max_salary || 0}));
const withSalary = jobs.filter(d => d.min_salary > 0 || d.max_salary > 0);
```

# Salary & Compensation

<div class="grid grid-cols-3">
  <div class="card">
    <h2>${withSalary.length.toLocaleString()}</h2>
    <span class="muted">Jobs With Salary Data</span>
  </div>
  <div class="card">
    <h2>${((jobs.length > 0) ? (withSalary.length / jobs.length * 100).toFixed(0) : 0)}%</h2>
    <span class="muted">Coverage Rate</span>
  </div>
  <div class="card">
    <h2>${withSalary.length > 0 ? "$" + Math.round(d3.mean(withSalary, d => d.min_salary)) : "—"}</h2>
    <span class="muted">Avg Min Salary (USD)</span>
  </div>
</div>

## Salary Range by Category

```js
const catMax = d3.rollup(withSalary, v => d3.max(v, d => d.max_salary), d => d.category);
const catOrder = Array.from(catMax).sort((a, b) => b[1] - a[1]).map(d => d[0]);

display(Plot.plot({
  marginLeft: 140,
  marginRight: 40,
  height: 400,
  y: {label: null, domain: catOrder},
  x: {label: "Salary (USD)", grid: true},
  color: {scheme: "Set2"},
  marks: [
    Plot.barX(withSalary, Plot.groupY({x1: "min", x2: "max"}, {x1: "min_salary", x2: "max_salary", y: "category", fill: "#ccc", tip: true})),
    Plot.ruleX([0])
  ]
}))
```

## Salary Distribution

```js
display(Plot.plot({
  height: 300,
  x: {label: "Salary (USD)"},
  y: {label: "Jobs"},
  marks: [
    Plot.rectY(withSalary, Plot.binX({y: "count"}, {x: "min_salary", fill: "steelblue", tip: true})),
    Plot.ruleY([0])
  ]
}))
```

## Jobs With Salary Data

```js
display(Inputs.table(withSalary.slice(0, 100), {
  columns: ["title", "company", "category", "min_salary", "max_salary", "currency"],
  header: {title: "Title", company: "Company", category: "Category", min_salary: "Min ($)", max_salary: "Max ($)", currency: "Currency"},
  sort: "min_salary",
  reverse: true,
  rows: 20,
}))
```

```js
const style = html`<style>
  .grid { display: grid; gap: 1rem; }
  .grid-cols-3 { grid-template-columns: repeat(3, 1fr); }
  .card { padding: 1rem; border: 1px solid #ddd; border-radius: 8px; background: var(--theme-background-secondary); }
  .card h2 { margin: 0; font-size: 1.8rem; }
  .muted { color: var(--theme-foreground-muted); }
  @media (max-width: 768px) { .grid-cols-3 { grid-template-columns: 1fr; } }
</style>`;
document.head.appendChild(style);
```
