---
title: Market Overview
---

```js
// Load all data files
const jobs = FileAttachment("data/jobs.csv").csv();
const techSkills = FileAttachment("data/technical_skills.csv").csv();
const softSkills = FileAttachment("data/soft_skills.csv").csv();
const quals = FileAttachment("data/qualifications.csv").csv();
const companies = FileAttachment("data/companies.csv").csv();
const categories = FileAttachment("data/categories.csv").csv();
const jobTypes = FileAttachment("data/job_types.csv").csv();
const experience = FileAttachment("data/experience.csv").csv();
const outcomes = FileAttachment("data/match_outcomes.csv").csv();
```

# Zimbabwe Job Market Intelligence

<div class="grid grid-cols-4">
  <div class="card">
    <h2>${jobs.length.toLocaleString()}</h2>
    <span class="muted">Total Jobs</span>
  </div>
  <div class="card">
    <h2>${techSkills.length.toLocaleString()}</h2>
    <span class="muted">Unique Technical Skills</span>
  </div>
  <div class="card">
    <h2>${companies.length.toLocaleString()}</h2>
    <span class="muted">Hiring Companies</span>
  </div>
  <div class="card">
    <h2>${categories.filter(d => d.job_count > 0).length}</h2>
    <span class="muted">Job Categories</span>
  </div>
</div>

## Top Technical Skills in Demand

```js
display(Plot.plot({
  marginLeft: 200,
  height: 500,
  y: {label: null, domain: techSkills.slice(0, 25).map(d => d.skill).reverse()},
  x: {label: "Jobs Requiring Skill"},
  marks: [
    Plot.barX(techSkills.slice(0, 25), {
      x: "job_count",
      y: "skill",
      sort: {y: "-x"},
      fill: "steelblue"
    }),
    Plot.text(techSkills.slice(0, 25), {
      x: "job_count",
      y: "skill",
      text: d => d.job_count,
      dx: 4,
      textAnchor: "start",
      fill: "white"
    })
  ]
}))
```

<div class="grid grid-cols-1">
  <div class="card">

### Top Soft Skills

```js
display(Plot.plot({
  marginLeft: 180,
  marginRight: 40,
  height: 350,
  y: {label: null, domain: softSkills.slice(0, 15).map(d => d.skill).reverse()},
  x: {label: "Jobs Requiring Skill"},
  marks: [
    Plot.barX(softSkills.slice(0, 15), {x: "job_count", y: "skill", fill: "#e15759"}),
    Plot.text(softSkills.slice(0, 15), {x: "job_count", y: "skill", text: d => d.job_count, dx: 3, textAnchor: "start", fill: "white"})
  ]
}))
```

  </div>
  <div class="card">

### Top Qualifications

```js
display(Plot.plot({
  marginLeft: 200,
  marginRight: 40,
  height: 350,
  y: {label: null, domain: quals.slice(0, 15).map(d => d.qualification).reverse()},
  x: {label: "Jobs Requiring"},
  marks: [
    Plot.barX(quals.slice(0, 15), {x: "job_count", y: "qualification", fill: "#4e79a7"}),
    Plot.text(quals.slice(0, 15), {x: "job_count", y: "qualification", text: d => d.job_count, dx: 3, textAnchor: "start", fill: "white"})
  ]
}))
```

  </div>
</div>

```js
// Style card grid
const style = html`<style>
  .grid { display: grid; gap: 1rem; }
  .grid-cols-2 { grid-template-columns: 1fr 1fr; }
  .grid-cols-4 { grid-template-columns: repeat(4, 1fr); }
  .card { padding: 1rem; border: 1px solid #ddd; border-radius: 8px; background: var(--theme-background-secondary); }
  .card h2 { margin: 0; font-size: 2rem; }
  .muted { color: var(--theme-foreground-muted); }
  @media (max-width: 768px) {
    .grid-cols-2, .grid-cols-4 { grid-template-columns: 1fr; }
  }
</style>`;
document.head.appendChild(style);
```
