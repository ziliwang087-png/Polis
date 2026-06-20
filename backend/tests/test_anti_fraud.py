"""
Unit tests for app.services.anti_fraud
"""
from datetime import datetime, timedelta
from uuid import uuid4

import pytest

from app.services import anti_fraud
from app.services.anti_fraud import (
    Alert, IPRegistration, ReviewContext, ReviewerHistory,
    rule_left_to_right, rule_mutual_review, rule_empty_task,
    rule_sock_puppet, rule_time_anomaly,
    severity_to_penalty,
)


# ------------------------- Pure rules -------------------------
def _ctx(**overrides):
    base = dict(
        owner_id=uuid4(), agent_id=uuid4(), task_id=uuid4(),
        rating=5,
        task_created_at=datetime.now() - timedelta(hours=1),
        task_completed_at=datetime.now(),
        task_description="A reasonably long task description that explains the requirement.",
        submission_content="A reasonably long submission with content showing actual work.",
        reward_points=20,
    )
    base.update(overrides)
    return ReviewContext(**base)


# ===== rule_left_to_right =====
def test_left_to_right_triggers_when_3plus_high_ratings():
    ctx = _ctx()
    history = ReviewerHistory(recent_tasks_with_agent=[
        {"task_id": uuid4(), "rating": 5, "created_at": datetime.now()},
        {"task_id": uuid4(), "rating": 5, "created_at": datetime.now()},
        {"task_id": uuid4(), "rating": 5, "created_at": datetime.now()},
    ])
    alert = rule_left_to_right(ctx, history)
    assert alert is not None
    assert alert.rule_name == "left_to_right"
    assert alert.severity >= 0.3
    assert alert.evidence["task_count_30d"] == 3
    assert alert.evidence["avg_rating"] >= 4.5


def test_left_to_right_silent_when_below_threshold():
    history = ReviewerHistory(recent_tasks_with_agent=[
        {"task_id": uuid4(), "rating": 5, "created_at": datetime.now()},
        {"task_id": uuid4(), "rating": 5, "created_at": datetime.now()},
    ])
    assert rule_left_to_right(_ctx(), history) is None


def test_left_to_right_silent_when_low_avg_rating():
    history = ReviewerHistory(recent_tasks_with_agent=[
        {"task_id": uuid4(), "rating": 3, "created_at": datetime.now()},
        {"task_id": uuid4(), "rating": 4, "created_at": datetime.now()},
        {"task_id": uuid4(), "rating": 4, "created_at": datetime.now()},
    ])
    assert rule_left_to_right(_ctx(), history) is None


def test_left_to_right_severity_grows_with_count():
    history = ReviewerHistory(recent_tasks_with_agent=[
        {"task_id": uuid4(), "rating": 5, "created_at": datetime.now()} for _ in range(10)
    ])
    a = rule_left_to_right(_ctx(), history)
    assert a is not None
    assert a.severity == 0.8  # capped


# ===== rule_mutual_review =====
def test_mutual_review_triggers_with_reverse_high_rating():
    history = ReviewerHistory(mutual_review_tasks=[
        {"task_id": uuid4(), "rating": 5},
        {"task_id": uuid4(), "rating": 4},
    ])
    a = rule_mutual_review(_ctx(rating=5), history)
    assert a is not None
    assert a.rule_name == "mutual_review"
    assert a.evidence["reverse_task_count"] == 2


def test_mutual_review_silent_when_low_current_rating():
    history = ReviewerHistory(mutual_review_tasks=[{"task_id": uuid4(), "rating": 5}])
    assert rule_mutual_review(_ctx(rating=2), history) is None


def test_mutual_review_silent_when_no_reverse():
    assert rule_mutual_review(_ctx(rating=5), ReviewerHistory()) is None


# ===== rule_empty_task =====
def test_empty_task_triggers_short_desc_high_reward():
    a = rule_empty_task(_ctx(
        task_description="lol",
        submission_content="ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok",
        reward_points=80,
    ))
    assert a is not None
    assert a.rule_name == "empty_task"
    assert a.severity >= 0.4


def test_empty_task_triggers_short_submission():
    a = rule_empty_task(_ctx(
        task_description="A real task description that is long enough and explains what to do clearly.",
        submission_content="done",
        reward_points=100,
    ))
    assert a is not None
    assert a.severity >= 0.4


def test_empty_task_silent_when_low_reward():
    a = rule_empty_task(_ctx(
        task_description="x", submission_content="y", reward_points=5,
    ))
    assert a is None


def test_empty_task_silent_with_real_content():
    a = rule_empty_task(_ctx(
        task_description="Build a website with login, registration, profile pages, and admin dashboard.",
        submission_content="Built the full site, deployed to staging, see attached repo and screenshots.",
        reward_points=200,
    ))
    assert a is None


# ===== rule_sock_puppet =====
def test_sock_puppet_triggers_when_same_ip():
    a = rule_sock_puppet(_ctx(rating=5), IPRegistration(
        owner_signup_ip="1.2.3.4",
        agent_owner_signup_ip="1.2.3.4",
    ))
    assert a is not None
    assert a.rule_name == "sock_puppet"
    assert a.evidence["shared_ip"] == "1.2.3.4"


def test_sock_puppet_silent_when_diff_ip():
    a = rule_sock_puppet(_ctx(), IPRegistration(
        owner_signup_ip="1.2.3.4",
        agent_owner_signup_ip="5.6.7.8",
    ))
    assert a is None


def test_sock_puppet_silent_when_missing_ip():
    a = rule_sock_puppet(_ctx(), IPRegistration(
        owner_signup_ip=None, agent_owner_signup_ip="1.2.3.4",
    ))
    assert a is None


# ===== rule_time_anomaly =====
def test_time_anomaly_triggers_under_5_min():
    now = datetime.now()
    a = rule_time_anomaly(_ctx(
        task_created_at=now - timedelta(minutes=2),
        task_completed_at=now,
    ))
    assert a is not None
    assert a.rule_name == "time_anomaly"
    assert a.evidence["elapsed_minutes"] < 5


def test_time_anomaly_extreme_severity_under_30s():
    now = datetime.now()
    a = rule_time_anomaly(_ctx(
        task_created_at=now - timedelta(seconds=10),
        task_completed_at=now,
    ))
    assert a is not None
    assert a.severity >= 0.7  # 0.4 + 0.3 + 0.2 = 0.9 capped


def test_time_anomaly_silent_when_long_enough():
    now = datetime.now()
    a = rule_time_anomaly(_ctx(
        task_created_at=now - timedelta(hours=2),
        task_completed_at=now,
    ))
    assert a is None


# ===== severity_to_penalty =====
def test_penalty_no_alerts_is_full():
    assert severity_to_penalty(0.0) == 1.0


def test_penalty_high_severity_capped_at_30pct():
    assert severity_to_penalty(5.0) == 0.3


def test_penalty_monotonic_decreasing():
    p1 = severity_to_penalty(0.2)
    p2 = severity_to_penalty(0.5)
    p3 = severity_to_penalty(1.0)
    assert p1 > p2 > p3


# ------------------------- Integration with FakeStore -------------------------
def test_check_review_for_fraud_left_to_right(conn, store):
    # 同 owner 给同 agent 发 4 个任务且每个都给 5 星
    o = store.add_owner()
    a = store.add_agent(o)
    for _ in range(4):
        t = store.add_task(o, a)
        store.add_review(t, rating=5)

    last_task = list(store.tasks.keys())[-1]
    alerts = anti_fraud.check_review_for_fraud(conn, o, a, last_task)
    rule_names = {x.rule_name for x in alerts}
    assert "left_to_right" in rule_names


def test_check_review_for_fraud_empty_task(conn, store):
    o = store.add_owner()
    a = store.add_agent(o)
    t = store.add_task(o, a, description="lol", reward_points=100)
    store.add_review(t, rating=5, submission_content="ok")
    alerts = anti_fraud.check_review_for_fraud(conn, o, a, t)
    rule_names = {x.rule_name for x in alerts}
    assert "empty_task" in rule_names


def test_check_review_for_fraud_time_anomaly(conn, store):
    o = store.add_owner()
    a = store.add_agent(o)
    now = datetime.now()
    t = store.add_task(
        o, a,
        created_at=now - timedelta(minutes=1),
        completed_at=now,
    )
    store.add_review(t, rating=5)
    alerts = anti_fraud.check_review_for_fraud(conn, o, a, t)
    rule_names = {x.rule_name for x in alerts}
    assert "time_anomaly" in rule_names


def test_check_review_for_fraud_sock_puppet(conn, store):
    same_ip = "10.0.0.1"
    o1 = store.add_owner(signup_ip=same_ip)
    o2 = store.add_owner(signup_ip=same_ip)
    a2 = store.add_agent(o2)
    t = store.add_task(o1, a2)
    store.add_review(t, rating=5)
    alerts = anti_fraud.check_review_for_fraud(conn, o1, a2, t)
    rule_names = {x.rule_name for x in alerts}
    assert "sock_puppet" in rule_names


def test_check_review_for_fraud_mutual_review(conn, store):
    """A 的 owner 给 B 的 agent 任务并给高分；B 的 owner 给 A 的 agent 也是高分。"""
    oA = store.add_owner()
    oB = store.add_owner()
    aA = store.add_agent(oA)
    aB = store.add_agent(oB)
    # B->A 的任务（已完成并打高分）
    t_BA = store.add_task(oB, aA)
    store.add_review(t_BA, rating=5)
    # A->B 的当前 review
    t_AB = store.add_task(oA, aB)
    store.add_review(t_AB, rating=5)
    alerts = anti_fraud.check_review_for_fraud(conn, oA, aB, t_AB)
    rule_names = {x.rule_name for x in alerts}
    assert "mutual_review" in rule_names


def test_check_review_for_fraud_normal_user_no_alerts(conn, store):
    # 不同 owner，单次任务，长描述长产出
    o = store.add_owner(signup_ip="1.1.1.1")
    o2 = store.add_owner(signup_ip="2.2.2.2")
    a = store.add_agent(o2)
    now = datetime.now()
    t = store.add_task(
        o, a,
        description="A complete task description that explains the work in detail with paragraphs of context",
        reward_points=10,
        created_at=now - timedelta(hours=3),
        completed_at=now,
    )
    store.add_review(t, rating=4, submission_content="A solid submission with code, screenshots, and tests linked")
    alerts = anti_fraud.check_review_for_fraud(conn, o, a, t)
    assert alerts == []


def test_reputation_score_with_penalty(conn, store):
    o = store.add_owner()
    a = store.add_agent(o)
    # 注入 reputation events
    store.reputation_events.append({
        "agent_id": a, "event_type": "task_completed", "points": 100,
        "zone": "work", "source_id": None, "verifiable": True,
        "created_at": datetime.now(),
    })
    store.reputation_events.append({
        "agent_id": a, "event_type": "follower_gained", "points": 50,
        "zone": "social", "source_id": None, "verifiable": False,
        "created_at": datetime.now(),
    })

    # 无告警时
    score_no_penalty = anti_fraud.update_reputation_score(conn, a)
    assert score_no_penalty["fraud_penalty"] == 1.0
    assert score_no_penalty["quality_score"] == 100
    assert score_no_penalty["social_score"] == 50
    # = 100*0.7 + 50*0.3 = 85
    assert score_no_penalty["total_score"] == 85

    # 注入一个 severity=0.5 的 alert
    from uuid import uuid4
    aid = uuid4()
    store.fraud_alerts[aid] = {
        "id": aid, "agent_id": a, "owner_id": o, "task_id": None,
        "rule_name": "left_to_right", "severity": 0.5,
        "evidence": {}, "status": "open", "reviewer_id": None,
        "reviewer_note": None, "detected_at": datetime.now(),
        "reviewed_at": None,
    }
    score_with_penalty = anti_fraud.update_reputation_score(conn, a)
    assert 0.7 <= score_with_penalty["fraud_penalty"] <= 0.8
    assert score_with_penalty["total_score"] < 85
