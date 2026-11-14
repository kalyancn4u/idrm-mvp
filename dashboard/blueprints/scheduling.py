"""Scheduling — shifts, trainings, certifications, calendar."""

from __future__ import annotations

from flask import Blueprint, render_template

from dashboard.extensions import db
from dashboard.security import permission_required
from dashboard.services.scheduling import SchedulingService

scheduling_bp = Blueprint("scheduling", __name__, template_folder="../templates")


@scheduling_bp.route("/shifts")
@permission_required("view.scheduling")
def shifts():
    svc = SchedulingService(db.session)
    rows = svc.upcoming_shifts()
    return render_template(
        "scheduling/shifts.html",
        shifts=[(s, svc.shift_signups_count(s.id)) for s in rows],
    )


@scheduling_bp.route("/trainings")
@permission_required("view.scheduling")
def trainings():
    svc = SchedulingService(db.session)
    return render_template(
        "scheduling/trainings.html",
        trainings=svc.trainings(),
        assignments=svc.training_assignments(),
        certifications=svc.certifications(),
    )


@scheduling_bp.route("/certifications")
@permission_required("view.scheduling")
def certifications():
    return render_template(
        "scheduling/certifications.html",
        certifications=SchedulingService(db.session).certifications(expiring_days=60),
    )
