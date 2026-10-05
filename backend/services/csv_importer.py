"""
CSV importer: reads the per-run CSV files (applied.csv + failed.csv) that the
agent wrote to (via temp config settings.file_name / failed_file_name) and
imports the rows into the job_applications table.

The agent writes to temp CSV paths set in the generated settings.py. After a
run completes, this importer reads those CSVs and upserts rows into the DB.
"""
from __future__ import annotations

import csv
import uuid
from pathlib import Path
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import AsyncSessionLocal
from db.models import AgentRun, JobApplication


async def import_run_csvs(run_id) -> dict:
    """
    Read the per-run applied.csv and failed.csv and import into job_applications.
    Returns a summary dict {applied: N, failed: N}.
    """
    summary = {"applied": 0, "failed": 0}

    async with AsyncSessionLocal() as db:
        # Get the run to find user_id
        result = await db.execute(select(AgentRun).where(AgentRun.id == run_id))
        run = result.scalar_one_or_none()
        if run is None:
            return summary
        user_id = run.user_id

        # The CSV paths are in the temp config dir; reconstruct from convention
        # (config_generator writes to <tempdir>/jp_csv_<run_id>/)
        # We stored temp_config_dir on the run record.
        csv_dir = None
        if run.temp_config_dir:
            # temp_config_dir is the root containing config/; CSVs are in tempdir/jp_csv_<run_id>/
            import tempfile
            csv_dir = Path(tempfile.gettempdir()) / f"jp_csv_{run_id}"
        if csv_dir is None or not csv_dir.exists():
            return summary

        applied_csv = csv_dir / "applied.csv"
        failed_csv = csv_dir / "failed.csv"

        # ---- Applied / external jobs ----
        if applied_csv.exists():
            with open(applied_csv, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    job_id = row.get("Job ID", "").strip()
                    if not job_id:
                        continue
                    # Determine status
                    ext_link = row.get("External Job link", "")
                    status = "applied" if ext_link in ("", "Easy Applied") else "external"
                    app = JobApplication(
                        run_id=run_id,
                        user_id=user_id,
                        job_id=job_id,
                        title=row.get("Title"),
                        company=row.get("Company"),
                        work_location=row.get("Work Location"),
                        work_style=row.get("Work Style"),
                        about_job=row.get("About Job"),
                        experience_required=row.get("Experience required"),
                        skills_required=_parse_list(row.get("Skills required")),
                        hr_name=row.get("HR Name"),
                        hr_link=row.get("HR Link"),
                        resume_filename=row.get("Resume"),
                        reposted=_parse_bool(row.get("Re-posted")),
                        date_posted=row.get("Date Posted"),
                        date_applied=row.get("Date Applied"),
                        job_link=row.get("Job Link"),
                        external_job_link=ext_link,
                        questions_found=_parse_questions(row.get("Questions Found")),
                        connect_request=row.get("Connect Request"),
                        status=status,
                    )
                    db.add(app)
                    summary["applied"] += 1

        # ---- Failed / skipped jobs ----
        if failed_csv.exists():
            with open(failed_csv, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    job_id = row.get("Job ID", "").strip()
                    if not job_id:
                        continue
                    reason = row.get("Assumed Reason", "")
                    # Classify: "Skipped" reason → skipped; "Blacklist" → rejected; else failed
                    if "Skipped" in reason:
                        status = "skipped"
                    elif "Blacklist" in reason:
                        status = "rejected"
                    else:
                        status = "failed"
                    app = JobApplication(
                        run_id=run_id,
                        user_id=user_id,
                        job_id=job_id,
                        title=None,
                        company=None,
                        job_link=row.get("Job Link"),
                        resume_filename=row.get("Resume Tried"),
                        date_posted=row.get("Date listed"),
                        status=status,
                        failure_reason=reason,
                        screenshot_name=row.get("Screenshot Name"),
                    )
                    db.add(app)
                    summary["failed"] += 1

        await db.commit()

    # Update run counters
    from sqlalchemy import update, func
    async with AsyncSessionLocal() as db:
        # Count by status for this run
        for status_val, col in [
            ("applied", "easy_applied_count"),
            ("external", "external_jobs_count"),
            ("failed", "failed_count"),
            ("skipped", "skip_count"),
        ]:
            cnt = (await db.execute(
                select(func.count()).select_from(JobApplication)
                .where(JobApplication.run_id == run_id, JobApplication.status == status_val)
            )).scalar_one()
            await db.execute(
                update(AgentRun).where(AgentRun.id == run_id).values(**{col: cnt})
            )
        await db.commit()

    return summary


def _parse_list(val) -> list:
    """Parse a CSV cell that may contain a list-like string."""
    if not val or val in ("In Development", "Needs an AI", "Error extracting skills"):
        return []
    try:
        import ast
        parsed = ast.literal_eval(val)
        return parsed if isinstance(parsed, list) else [str(parsed)]
    except Exception:
        return [val] if val else []


def _parse_bool(val) -> bool:
    if not val:
        return False
    return str(val).strip().lower() in ("true", "1", "yes")


def _parse_questions(val):
    """Parse the Questions Found CSV cell into a JSON-serializable structure."""
    if not val or val == "None":
        return None
    try:
        import ast
        return ast.literal_eval(val)
    except Exception:
        return {"raw": val}
