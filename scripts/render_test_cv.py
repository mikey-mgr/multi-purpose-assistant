"""Render the active candidate profile without calling an LLM.

Usage:
    python scripts/render_test_cv.py --email candidate@example.com
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.rag import _fetch_profile_with_pydantic
from app.rendercv_renderer import build_yaml_dict, render
from core.database import User, get_session


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True, help="Email address of the candidate to render")
    parser.add_argument("--job-title", default="Test CV", help="Label used in the output filename")
    args = parser.parse_args()

    session = get_session()
    try:
        user = session.query(User).filter(User.email == args.email).one_or_none()
        if user is None:
            raise SystemExit(f"No candidate exists for {args.email}")
        user_id = user.id
    finally:
        session.close()

    profile_data = _fetch_profile_with_pydantic(user_id)
    cv = build_yaml_dict(
        user=profile_data["user"],
        resume=profile_data["resume"],
        experiences=profile_data["experiences"],
        education=profile_data["education"],
        certifications=profile_data["certifications"],
        projects=profile_data["projects"],
        skills=profile_data["skills"],
    )
    print(render(cv, job_title=args.job_title))


if __name__ == "__main__":
    main()
