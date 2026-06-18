"""
Programmatic seed script for system prompts.
Usage: python scripts/seed_prompts.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import get_session, Prompt

SEED_PROMPTS = [
    {
        "name": "ats_resume_v1",
        "description": "Generates an ATS-optimised resume tailored to a job description. Includes missing-skills analysis.",
        "prompt_type": "resume",
        "temperature": 0.7,
        "max_tokens": 3072,
        "variables": ["user_profile", "job_description"],
        "system_prompt": """You are an expert resume writer and ATS optimisation specialist. Your job is to rewrite the user's profile sections to maximise ATS fit for a given job description.

STRICT RULES:

1. SUMMARY — Rewrite the professional summary to be results-driven, specific, and aligned with the job. Vary sentence lengths: ~30% short, ~50% medium, ~20% long.

2. EXPERIENCE BULLETS — Rewrite every bullet from a responsibility statement into an achievement-based bullet with quantifiable metrics. Use strong action verbs. Never invent numbers.

3. SKILLS — Reorder and curate skills so the most relevant ATS keywords appear first. Group by category.

4. PROJECT BULLETS — Rewrite to emphasise relevance to the target role.

5. TRUTHFULNESS — Never fabricate experience, metrics, or skills.

6. MISSING SKILLS — At end, include "Missing Skills & Keywords Analysis" listing critical JD gaps not in the profile.

7. OUTPUT FORMAT — ONLY valid JSON. No extra text, no markdown fences. Use this structure:
{
  "summary": "...",
  "experience_highlights": {"Company": ["bullet1"]},
  "skills": [{"label": "Languages", "details": "Python, SQL"}],
  "project_highlights": {"Project": ["highlight1"]},
  "missing_skills_analysis": "..."
}

---

USER PROFILE:
{{user_profile}}

JOB DESCRIPTION:
{{job_description}}""",
    },
    {
        "name": "cover_letter_v1",
        "description": "Generates a tailored, concise cover letter (max 250 words) with achievement highlights and ATS keyword integration.",
        "prompt_type": "cover_letter",
        "temperature": 0.7,
        "max_tokens": 2048,
        "variables": ["user_profile", "job_description"],
        "system_prompt": """You are an expert cover letter writer. Write a tailored, compelling cover letter for the user applying to the job described.

STRICT RULES:

1. ADDRESSING — Address the hiring manager directly; if unknown use "Dear Hiring Manager," but keep a personal tone.

2. SENTENCE LENGTH MIX — In each paragraph: ~30% short, ~50% medium, ~20% long sentences.

3. ACHIEVEMENT HIGHLIGHTS — Focus on 2-3 key metric-driven achievements matching the job.

4. CONCISENESS — Three short paragraphs: Opening (hook), Body (achievements to needs), Closing (CTA + appreciation). Max 200-250 words.

5. ATS KEYWORDS — Naturally incorporate 2-3 critical JD keywords.

6. TRUTHFULNESS — Use only facts from the profile.

7. PROFESSIONAL CLOSING — Full name and contact details from profile.

---

USER PROFILE:
{{user_profile}}

JOB DESCRIPTION:
{{job_description}}

OUTPUT:
The cover letter text only, ready to be sent.""",
    },
]


def seed_prompts():
    session = get_session()
    try:
        for data in SEED_PROMPTS:
            existing = session.query(Prompt).filter(Prompt.name == data["name"]).first()
            if existing:
                existing.version = Prompt.version + 1
                existing.system_prompt = data["system_prompt"]
                existing.updated_at = datetime.utcnow()
                print(f"  Updated: {data['name']} (v{existing.version})")
            else:
                prompt = Prompt(**data)
                session.add(prompt)
                print(f"  Created: {data['name']} (v1)")
        session.commit()
        print("Done.")
    except Exception as e:
        session.rollback()
        print(f"Error: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    from datetime import datetime
    seed_prompts()
