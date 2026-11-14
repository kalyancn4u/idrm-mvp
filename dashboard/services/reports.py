"""Rollup reports."""

from __future__ import annotations

from sqlalchemy import text


class ReportService:
    def __init__(self, session):
        self.db = session

    def daily_created(self, days: int = 30) -> list[dict]:
        rows = self.db.execute(
            text(
                """
                SELECT date_trunc('day', created_at) AS day,
                       count(*) AS created,
                       count(*) FILTER (WHERE status = 'verified') AS verified
                  FROM incidents
                 WHERE created_at > now() - make_interval(days => :d)
                   AND deleted_at IS NULL
                 GROUP BY day ORDER BY day DESC
                """
            ),
            {"d": days},
        ).mappings().all()
        return [dict(r) for r in rows]

    def response_times(self, days: int = 30) -> list[dict]:
        """Average minutes from creation to the citizen's verification, per day."""
        rows = self.db.execute(
            text(
                """
                SELECT date_trunc('day', created_at) AS day,
                       avg(EXTRACT(EPOCH FROM (verified_at - created_at)) / 60)
                         FILTER (WHERE verified_at IS NOT NULL) AS avg_minutes
                  FROM incidents
                 WHERE created_at > now() - make_interval(days => :d)
                   AND deleted_at IS NULL
                 GROUP BY day ORDER BY day DESC
                """
            ),
            {"d": days},
        ).mappings().all()
        return [dict(r) for r in rows]

    def top_organizations(self, limit: int = 10) -> list[dict]:
        rows = self.db.execute(
            text(
                """
                SELECT o.id, o.name, o.is_verified,
                       count(i.id) AS assigned,
                       count(i.id) FILTER (WHERE i.status = 'verified') AS verified
                  FROM organizations o
                  LEFT JOIN incidents i ON i.assigned_organization_id = o.id
                                       AND i.deleted_at IS NULL
                 WHERE o.deleted_at IS NULL
                 GROUP BY o.id
                 ORDER BY verified DESC, assigned DESC
                 LIMIT :lim
                """
            ),
            {"lim": limit},
        ).mappings().all()
        return [dict(r) for r in rows]

