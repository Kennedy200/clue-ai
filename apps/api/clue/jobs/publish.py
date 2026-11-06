"""Background job: upload a finished video to YouTube."""
from __future__ import annotations

from sqlalchemy.orm import Session

from clue.core.ids import utcnow
from clue.jobs.registry import handler
from clue.models import Job, Project, ScheduledPost


class PublishError(Exception):
    retryable = False


@handler("youtube_publish")
def youtube_publish(db: Session, job: Job) -> dict:
    from clue.api import youtube

    p = job.payload
    project = db.get(Project, p["project_id"])
    if project is None or not project.output_path:
        raise PublishError("The video file is missing.")
    try:
        url = youtube.upload(db, job.user_id, project, p["title"], p.get("description", ""), p.get("privacy", "private"))
    except RuntimeError as e:
        raise PublishError(str(e)) from e
    if p.get("post_id"):
        post = db.get(ScheduledPost, p["post_id"])
        if post and post.user_id == job.user_id:
            post.status, post.external_url = "published", url
            db.commit()
    return {"url": url, "at": utcnow().isoformat()}
