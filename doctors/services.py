from collections import defaultdict
from datetime import datetime, timedelta

from django.db import transaction
from django.utils import timezone

from .models import Availability

SLOT_HORIZON_DAYS = 30


def _is_blocked(exceptions, start_time, end_time):
    return any(exception.blocks(start_time, end_time) for exception in exceptions)


@transaction.atomic
def rebuild_availability(doctor, days=SLOT_HORIZON_DAYS):
    """Recreate future slots after the doctor changes weekly hours or exceptions."""

    today = timezone.localdate()
    doctor.slots.filter(date__gte=today).delete()
    return generate_availability(doctor, days=days)


def generate_availability(doctor, days=SLOT_HORIZON_DAYS, start_date=None):
    """Create missing slots for the horizon; returns the number of new slots."""

    today = timezone.localdate()
    first_day = max(start_date or today, today)
    last_day = first_day + timedelta(days=days - 1)

    weekly_hours = defaultdict(list)
    for row in doctor.weekly_hours.filter(is_active=True):
        weekly_hours[row.weekday].append(row)

    exceptions = defaultdict(list)
    for exception in doctor.exceptions.filter(date__range=(first_day, last_day)):
        exceptions[exception.date].append(exception)

    duration = timedelta(minutes=doctor.consultation_duration)
    now = timezone.localtime()
    existing = set(
        doctor.slots.filter(date__range=(first_day, last_day)).values_list("date", "start_time")
    )

    new_slots = []
    for offset in range(days):
        day = first_day + timedelta(days=offset)
        rows = sorted(weekly_hours[day.weekday()], key=lambda row: row.start_time)
        for row in rows:
            cursor = datetime.combine(day, row.start_time)
            limit = datetime.combine(day, row.end_time)
            while cursor + duration <= limit:
                start_time = cursor.time()
                end_time = (cursor + duration).time()
                if day == today and start_time <= now.time():
                    cursor += duration
                    continue
                if (day, start_time) in existing or _is_blocked(
                    exceptions[day], start_time, end_time
                ):
                    cursor += duration
                    continue
                new_slots.append(
                    Availability(
                        doctor=doctor,
                        date=day,
                        start_time=start_time,
                        end_time=end_time,
                    )
                )
                cursor += duration

    Availability.objects.bulk_create(new_slots, ignore_conflicts=True)
    return len(new_slots)


def upcoming_slots(doctor, days=14):
    """Return generated slots grouped by day for the public profile."""

    generate_availability(doctor, days=days)
    today = timezone.localdate()
    limit = today + timedelta(days=days - 1)
    grouped = []
    current_date = None
    for slot in doctor.slots.filter(date__range=(today, limit)).order_by("date", "start_time"):
        if slot.date != current_date:
            current_date = slot.date
            grouped.append({"date": slot.date, "slots": []})
        grouped[-1]["slots"].append(slot)
    return grouped
