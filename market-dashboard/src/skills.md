---
title: Skills & Qualifications
---

```js
const techSkills = FileAttachment("data/technical_skills.csv").csv();
const softSkills = FileAttachment("data/soft_skills.csv").csv();
const quals = FileAttachment("data/qualifications.csv").csv();
const jobs = FileAttachment("data/jobs.csv").csv();
```

# Skills & Qualifications

## Technical Skills — Full Ranking

When applying for jobs in Zimbabwe, these are the skills employers ask for most.

```js
// Category detection helper
function detectCategory(skill) {
  const s = skill.toLowerCase();
  if (/excel|word|outlook|powerpoint|microsoft|office/.test(s)) return "Office & Productivity";
  if (/sap|erp|dynamics|pastel|sage/.test(s)) return "ERP / Accounting";
  if (/python|java|sql|javascript|html|css|react|node|django/.test(s)) return "Programming";
  if (/autocad|civil|irrigation|engineering|mechanical|electrical/.test(s)) return "Engineering / Design";
  if (/crm|customer.*relat|salesforce/.test(s)) return "CRM / Sales";
  if (/seo|social media|content|graphic design|video|adobe|photoshop|premiere/.test(s)) return "Marketing / Media";
  if (/gis|remote sensing|data.*analytics|data.*science/.test(s)) return "Data & Analytics";
  if (/network|firewall|server|cloud|vpn|help.?desk|comp.?tia|itil/.test(s)) return "IT Infrastructure";
  return "Other";
}

const techWithCategory = techSkills.map(d => ({...d, category: detectCategory(d.skill)}));
```

### By Skill Category

```js
const catTotals = d3.rollup(techWithCategory, v => d3.sum(v, d => d.job_count), d => d.category);
const catData = Array.from(catTotals, ([category, job_count]) => ({category, job_count})).sort((a,b) => b.job_count - a.job_count);

display(Plot.plot({
  marginLeft: 140,
  marginRight: 40,
  height: 300,
  y: {label: null, domain: catData.map(d => d.category).reverse()},
  x: {label: "Jobs Requiring Skill"},
  color: {scheme: "Set3"},
  marks: [
    Plot.barX(catData, {x: "job_count", y: "category", fill: "category", tip: true}),
    Plot.text(catData, {x: "job_count", y: "category", text: d => d.job_count, dx: 3, textAnchor: "start", fill: "white"})
  ]
}))
```

### Top 30 Technical Skills

```js
display(Plot.plot({
  marginLeft: 200,
  height: 600,
  y: {label: null, domain: techSkills.slice(0, 30).map(d => d.skill).reverse()},
  x: {label: "Jobs Requiring Skill"},
  marks: [
    Plot.barX(techSkills.slice(0, 30), {x: "job_count", y: "skill", fill: "steelblue"}),
    Plot.text(techSkills.slice(0, 30), {x: "job_count", y: "skill", text: d => d.job_count, dx: 3, textAnchor: "start", fill: "white"})
  ]
}))
```

## Soft Skills

```js
display(Plot.plot({
  marginLeft: 200,
  marginRight: 40,
  height: 400,
  y: {label: null, domain: softSkills.slice(0, 20).map(d => d.skill).reverse()},
  x: {label: "Jobs Requiring Skill"},
  marks: [
    Plot.barX(softSkills.slice(0, 20), {x: "job_count", y: "skill", fill: "#e15759"}),
    Plot.text(softSkills.slice(0, 20), {x: "job_count", y: "skill", text: d => d.job_count, dx: 3, textAnchor: "start", fill: "white"})
  ]
}))
```

## Qualifications & Certifications

```js
display(Plot.plot({
  marginLeft: 250,
  marginRight: 40,
  height: 500,
  y: {label: null, domain: quals.slice(0, 25).map(d => d.qualification).reverse()},
  x: {label: "Jobs Requiring"},
  marks: [
    Plot.barX(quals.slice(0, 25), {x: "job_count", y: "qualification", fill: "#4e79a7"}),
    Plot.text(quals.slice(0, 25), {x: "job_count", y: "qualification", text: d => d.job_count, dx: 3, textAnchor: "start", fill: "white"})
  ]
}))
```

```js
const style = html`<style>
  .grid { display: grid; gap: 1rem; }
  .grid-cols-2 { grid-template-columns: 1fr 1fr; }
  .card { padding: 1rem; border: 1px solid #ddd; border-radius: 8px; background: var(--theme-background-secondary); }
  @media (max-width: 768px) { .grid-cols-2 { grid-template-columns: 1fr; } }
</style>`;
document.head.appendChild(style);
```
