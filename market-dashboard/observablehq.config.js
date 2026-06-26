export default {
  root: "src",
  output: "dist",
  title: "Zimbabwe Job Market Intelligence",
  head: `<style>
    @media (max-width: 768px) {
      svg.observablehq text { font-size: 14px !important; }
      table, .observablehq table { font-size: 13px !important; }
      .card h2 { font-size: 1.4rem !important; }
    }
  </style>`,
  pages: [
    { name: "Overview", path: "/" },
    { name: "Skills & Qualifications", path: "/skills" },
    { name: "Salary & Compensation", path: "/salaries" },
    { name: "Companies & Categories", path: "/companies" },
    { name: "Job Types & Experience", path: "/job-types" },
  ],
};
