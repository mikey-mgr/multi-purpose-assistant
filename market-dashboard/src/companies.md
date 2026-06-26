---
title: Companies & Categories
---

```js
const companies = FileAttachment("data/companies.csv").csv();
const categories = FileAttachment("data/categories.csv").csv();
const jobs = FileAttachment("data/jobs.csv").csv();
```

# Companies & Categories

## Hiring Companies

```js
display(Plot.plot({
  marginLeft: 200,
  height: 500,
  y: {label: null, domain: companies.slice(0, 30).map(d => d.company).reverse()},
  x: {label: "Jobs Posted"},
  marks: [
    Plot.barX(companies.slice(0, 30), {x: "job_count", y: "company", fill: "#76b7b2", tip: true}),
    Plot.text(companies.slice(0, 30), {x: "job_count", y: "company", text: d => d.job_count, dx: 3, textAnchor: "start", fill: "white"})
  ]
}))
```

<div class="card-full">

## Job Categories

```js
display(Plot.plot({
  marginLeft: 200,
  marginRight: 40,
  height: 500,
  y: {label: null, domain: categories.slice().sort((a,b) => b.job_count - a.job_count).map(d => d.category).reverse()},
  x: {label: "Jobs"},
  color: {scheme: "Set3"},
  marks: [
    Plot.barX(categories, {x: "job_count", y: "category", fill: "category", tip: true}),
    Plot.text(categories, {x: "job_count", y: "category", text: d => d.job_count, dx: 3, textAnchor: "start", fill: "white"})
  ]
}))
```

</div>

## Browse Jobs

```js
display(Inputs.table(jobs.slice(0, 200), {
  columns: ["title", "company", "category", "date_posted"],
  header: {title: "Title", company: "Company", category: "Category", date_posted: "Posted"},
  sort: "date_posted",
  reverse: true,
  rows: 20,
}))
```

```js
const style = html`<style>
  .grid { display: grid; gap: 1rem; }
  .grid-cols-2 { grid-template-columns: 1fr 1fr; }
  .card { padding: 1rem; border: 1px solid #ddd; border-radius: 8px; background: var(--theme-background-secondary); }
  .card-full { padding: 1rem; border: 1px solid #ddd; border-radius: 8px; background: var(--theme-background-secondary); margin-bottom: 1rem; }
  @media (max-width: 768px) { .grid-cols-2 { grid-template-columns: 1fr; } }
</style>`;
document.head.appendChild(style);
```
