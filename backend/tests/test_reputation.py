"""
Unit tests for reputation aggregation: severity_to_penalty + update_reputation_score.
"""
from datetime import datetime
from uuid import uuid4

import pytest

from app.services import anti_fraud


def test_basic_quality_only(conn, store):
    o = store.add_owner()
    a = store.add_agent(o)
    store.reputation_events.append({
        "agent_id": a, "event_type": "task_completed", "points": 80,
        "zone": "work", "source_id": None, "verifiable": True,
        "created_at": datetime.now(),
    })
    s = anti_fraud.update_reputation_score(conn, a)
    assert s["quality_score"] == 80
    assert s["social_score"] == 0
    assert s["total_score"] == 56  # 80*0.7 + 0 = 56


def test_basic_social_only(conn, store):
    o = store.add_owner()
    a = store.add_agent(o)
    store.reputation_events.append({
        "agent_id": a, "event_type": "follower_gained", "points": 100,
        "zone": "social", "source_id": None, "verifiable": False,
        "created_at": datetime.now(),
    })
    s = anti_fraud.update_reputation_score(conn, a)
    assert s["social_score"] == 100
    assert s["quality_score"] == 0
    assert s["total_score"] == 30  # 100*0.3 = 30


def test_dual_track_combination(conn, store):
    o = store.add_owner()
    a = store.add_agent(o)
    store.reputation_events.append({
        "agent_id": a, "event_type": "task_completed", "points": 100,
        "zone": "work", "source_id": None, "verifiable": True,
        "created_at": datetime.now(),
    })
    store.reputation_events.append({
        "agent_id": a, "event_type": "follower_gained", "points": 100,
        "zone": "social", "source_id": None, "verifiable": False,
        "created_at": datetime.now(),
    })
    s = anti_fraud.update_reputation_score(conn, a)
    # 100*0.7 + 100*0.3 = 100
    assert s["total_score"] == 100


def test_penalty_reduces_score(conn, store):
    o = store.add_owner()
    a = store.add_agent(o)
    store.reputation_events.append({
        "agent_id": a, "event_type": "task_completed", "points": 100,
        "zone": "work", "source_id": None, "verifiable": True,
        "created_at": datetime.now(),
    })

    # 注入 severity=1.0 alert
    aid = uuid4()
    store.fraud_alerts[aid] = {
        "id": aid, "agent_id": a, "owner_id": o, "task_id": None,
        "rule_name": "left_to_right", "severity": 1.0,
        "evidence": {}, "status": "open", "reviewer_id": None,
        "reviewer_note": None, "detected_at": datetime.now(),
        "reviewed_at": None,
    }
    s = anti_fraud.update_reputation_score(conn, a)
    # severity=1.0 -> penalty = max(0.3, 1.0 - 0.5*1.0) = 0.5
    assert s["fraud_penalty"] == 0.5
    # 100*0.7 = 70 * 0.5 = 35
    assert s["total_score"] == 35


def test_dismissed_alert_does_not_penalize(conn, store):
    o = store.add_owner()
    a = store.add_agent(o)
    store.reputation_events.append({
        "agent_id": a, "event_type": "task_completed", "points": 100,
        "zone": "work", "source_id": None, "verifiable": True,
        "created_at": datetime.now(),
    })
    aid = uuid4()
    store.fraud_alerts[aid] = {
        "id": aid, "agent_id": a, "owner_id": o, "task_id": None,
        "rule_name": "left_to_right", "severity": 1.0,
        "evidence": {}, "status": "dismissed", "reviewer_id": None,
        "reviewer_note": None, "detected_at": datetime.now(),
        "reviewed_at": datetime.now(),
    }
    s = anti_fraud.update_reputation_score(conn, a)
    assert s["fraud_penalty"] == 1.0
    assert s["total_score"] == 70


def test_per_rule_dedup(conn, store):
    """同一规则的多条 alert 只取最严重那条，避免重复扣分"""
    o = store.add_owner()
    a = store.add_agent(o)
    store.reputation_events.append({
        "agent_id": a, "event_type": "task_completed", "points": 100,
        "zone": "work", "source_id": None, "verifiable": True,
        "created_at": datetime.now(),
    })

    # 三条同 rule 的 alert
    for sev in (0.3, 0.5, 0.4):
        aid = uuid4()
        store.fraud_alerts[aid] = {
            "id": aid, "agent_id": a, "owner_id": o, "task_id": None,
            "rule_name": "left_to_right", "severity": sev,
            "evidence": {}, "status": "open", "reviewer_id": None,
            "reviewer_note": None, "detected_at": datetime.now(),
            "reviewed_at": None,
        }
    s = anti_fraud.update_reputation_score(conn, a)
    # 应当只算 max severity = 0.5: penalty = 0.75
    assert s["fraud_penalty"] == 0.75
