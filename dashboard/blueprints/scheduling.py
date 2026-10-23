"""Scheduling — shifts, trainings, certifications, calendar."""

from __future__ import annotations

from flask import Blueprint, render_template
from flask_login import login_required

from dashboard.extensions import db
from dashboard.services.scheduling import SchedulingService

scheduling_bp = Blueprint("scheduling", __name__, template_folder="../templates")


@scheduling_bp.route("/shifts")
@login_required
def shifts():
    svc = SchedulingService(db.session)
    rows = svc.upcoming_shifts()
    return render_template(
        "scheduling/shifts.html",
        shifts=[(s, svc.shift_signups_count(s.id)) for s in rows],
    )


@scheduling_bp.route("/trainings")
@login_required
def trainings():
    svc = SchedulingService(db.session)
    return render_template(
        "scheduling/trainings.html",
        trainings=svc.trainings(),
        assignments=svc.training_assignments(),
        certifications=svc.certifications(),
    )

