# RenderCV Integration — Issues & Fixes

## 1. LLM Resume Overrides Not Applied

**Problem**: The `ats_and_cover_v1` prompt said `"resume": { ... same resume structure as before ... }` — too vague. The LLM didn't output the override keys that `build_yaml_dict` expects, so skills, experience bullets, and project bullets came raw from the DB instead of AI-adapted text.

**Fix**:
- Prompt now specifies the exact override structure:
  ```json
  {
    "resume": {
      "summary": "...",
      "experience_highlights": {"Company": ["bullet1", "bullet2"]},
      "skills": [{"label": "Category", "details": "item1, item2"}],
      "project_highlights": {"Project": ["bullet1", "bullet2"]}
    }
  }
  ```
- `build_yaml_dict` validates `skills` override is a list of `{label, details}` dicts before using it; falls back to DB grouping otherwise.

## 2. Education Degree/Area Duplication

**Problem**: `area` was set to `f"{degree} in {field}"` (e.g., "BSc (Hons) in Information Technology") AND `degree` was also set separately. RenderCV's `DEGREE_WITH_AREA` template combined both, producing "BSc (Hons) in BSc (Hons) in Information Technology".

**Fix**: `area` is now just the field of study (`field`), `degree` is the degree type. RenderCV's locale-aware `DEGREE_WITH_AREA` combines them correctly.

## 3. Project Link Not Rendering

**Problem**: RenderCV v2.x `NormalEntry` (used for projects) has no `url` field. The old `(Link)` hack was text-only. The `[Project Link](url)` bullet approach broke PDF generation and put the link as a bullet item.

**Fix**: Keep `(Link)` appended to the project name as plain text. Markdown links aren't supported in NormalEntry's name field, and adding arbitrary fields causes YAML validation errors.

## 4. RenderCV v2.x Output Path Changed

**Problem**: v1.x output files went to `{stem}/{stem}_cv.pdf`. v2.x outputs to the YAML's parent directory as `{Name_Snake_Case_CV}.pdf`. The `--output-folder` flag is ignored in the installed version.

**Fix**: Look for PDFs via glob `*CV*.pdf` in the YAML's parent directory, not in a stem-named subfolder.

## 5. RenderCV v2.x Errors Go to stdout

**Problem**: v2.x prints validation errors through `rich.panel` to stdout, not stderr. Our code only logged stderr, hiding the actual error messages.

**Fix**: Log both `result.stderr` and `result.stdout` on failure.

## 6. Section Type Detection Requires All Characteristic Fields

**Problem**: RenderCV v2.x auto-detects entry types by characteristic fields (e.g., `EducationEntry` needs `institution`, `area`, AND `degree` keys). Missing `degree` caused detection failure. Skills need `label` AND `details` dicts, not flat strings.

**Fix**: Added `degree` to education entries. Validated skills override structure before use.

## To Reapply

After pulling these changes, run `python scripts/seed_prompts.py` to update the prompts in the database.
