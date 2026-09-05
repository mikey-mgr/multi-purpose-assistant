"""Validate or import a canonical candidate profile YAML file."""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.candidate_import import import_candidate_profile, load_candidate_profile, profile_summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile", help="Path to candidate profile YAML")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write a confirmed profile to PostgreSQL. Without this flag, validation is read-only.",
    )
    args = parser.parse_args()

    profile = load_candidate_profile(args.profile)
    print(json.dumps(profile_summary(profile), indent=2))

    if not args.apply:
        print("Validation passed. No database changes were made.")
        return

    user_id, resume_id = import_candidate_profile(profile)
    print(json.dumps({"user_id": user_id, "resume_id": resume_id}, indent=2))


if __name__ == "__main__":
    main()
