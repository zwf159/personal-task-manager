from . import repository as repo


def candidate_issues(db, slot, exclude=0, pending=()):
    issues = []
    overlap = repo.overlapping(db, slot, exclude)
    if overlap:
        issues.append(
            {"code": "overlap", "message": "与已有计划重叠", "items": overlap}
        )
    for planned in pending:
        if (
            planned["day"] == slot["day"]
            and planned["start_minute"] < slot["end_minute"]
            and planned["end_minute"] > slot["start_minute"]
        ):
            issues.append(
                {
                    "code": "batch_overlap",
                    "message": "与本批次另一安排重叠",
                    "items": [],
                }
            )
            break
    state = repo.day_state(db, slot["day"])
    removed = next(
        (
            row["end_minute"] - row["start_minute"]
            for row in state["slots"]
            if row["id"] == exclude
        ),
        0,
    )
    additions = sum(
        row["end_minute"] - row["start_minute"]
        for row in pending
        if row["day"] == slot["day"]
    )
    desired = (
        state["scheduled"]
        - removed
        + additions
        + slot["end_minute"]
        - slot["start_minute"]
    )
    if desired > state["capacity"]:
        issues.append(
            {
                "code": "capacity",
                "message": f"当天需要 {desired} 分钟，超过容量 {state['capacity']} 分钟",
                "items": [],
            }
        )
    if slot["task_id"] is not None:
        task = db.execute(
            "SELECT deleted_at FROM tasks WHERE id=?", (slot["task_id"],)
        ).fetchone()
        if task is None or task["deleted_at"]:
            issues.append(
                {
                    "code": "task_unavailable",
                    "message": "关联任务不存在或已回收",
                    "items": [],
                }
            )
    return issues


def suggestions(db, slot, exclude=0):
    preferences = repo.settings(db)
    start = preferences["start_hour"] * 60
    end = preferences["end_hour"] * 60
    duration = slot["end_minute"] - slot["start_minute"]
    occupied = [
        row for row in repo.day_state(db, slot["day"])["slots"] if row["id"] != exclude
    ]
    cursor = start
    result = []
    for row in [*occupied, {"start_minute": end, "end_minute": end}]:
        gap_end = min(row["start_minute"], end)
        candidate = {**slot, "start_minute": cursor, "end_minute": cursor + duration}
        if cursor + duration <= gap_end and not candidate_issues(
            db, candidate, exclude
        ):
            result.append(
                {
                    "day": slot["day"],
                    "start_minute": cursor,
                    "end_minute": cursor + duration,
                }
            )
        cursor = max(cursor, row["end_minute"])
        if cursor >= end or len(result) >= 3:
            break
    return result


def classify(db, candidates):
    accepted = []
    conflicts = []
    duplicates = []
    for candidate in candidates:
        duplicate = db.execute(
            "SELECT id FROM plan_slots WHERE day=? AND title=? AND start_minute=? AND end_minute=? AND task_id IS ? AND note=?",
            (
                candidate["day"],
                candidate["title"],
                candidate["start_minute"],
                candidate["end_minute"],
                candidate["task_id"],
                candidate["note"],
            ),
        ).fetchone()
        if duplicate:
            duplicates.append({**candidate, "existing_id": duplicate["id"]})
            continue
        issues = candidate_issues(db, candidate, 0, accepted)
        if issues:
            conflicts.append(
                {
                    "slot": candidate,
                    "issues": issues,
                    "suggestions": suggestions(db, candidate),
                }
            )
        else:
            accepted.append(candidate)
    return {"accepted": accepted, "conflicts": conflicts, "duplicates": duplicates}
