#!/usr/bin/env python3
"""
demo_anti_fraud.py — 防刷算法 4 场景演示。

目的：不连真实 DB，用 in-memory FakeStore 跑通 5 条规则。
方便 reviewer 一眼看到「输入什么 → 触发什么 → 严重度多少 → 信誉折扣多少」。

跑法：
    cd backend
    source venv/bin/activate
    python demo_anti_fraud.py
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

# 让 app.* 可导入
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from tests.conftest import FakeConnection, FakeStore  # noqa: E402
from app.services import anti_fraud  # noqa: E402


# -----------------------------------------------------------------
# Pretty printer
# -----------------------------------------------------------------
def banner(title: str):
    print()
    print("=" * 68)
    print(f"  {title}")
    print("=" * 68)


def show_alerts(alerts):
    if not alerts:
        print("  ✓ no alerts triggered")
        return
    for a in alerts:
        print(f"  • [{a.rule_name:18s}] severity={a.severity:.2f}")
        for k, v in a.evidence.items():
            print(f"      {k}: {v}")


def show_score(conn, agent_id, label):
    s = anti_fraud.update_reputation_score(conn, agent_id)
    print(
        f"  reputation[{label}] "
        f"quality={s['quality_score']} social={s['social_score']} "
        f"penalty={s['fraud_penalty']:.2f} -> total={s['total_score']}"
    )


# -----------------------------------------------------------------
# Scenario 1: 正常用户
# -----------------------------------------------------------------
def scenario_normal_user():
    banner("Scenario 1 — 正常用户：3 任务 + 真实评分")
    store = FakeStore()
    conn = FakeConnection(store)

    o1 = store.add_owner(signup_ip="1.1.1.1")
    o2 = store.add_owner(signup_ip="2.2.2.2")
    a = store.add_agent(o2, name="GoodBot")

    # 3 个任务，每个相隔 7 天，长描述长产出
    base = datetime.now() - timedelta(days=20)
    for i, rating in enumerate([4, 5, 4]):
        created = base + timedelta(days=i * 7)
        completed = created + timedelta(hours=4)
        t = store.add_task(
            o1, a,
            description=(
                "Build a working microservice with REST API, database "
                "integration, JWT auth, comprehensive tests, and CI pipeline."
            ),
            reward_points=30,
            created_at=created,
            completed_at=completed,
        )
        store.add_review(
            t, rating=rating,
            submission_content=(
                "Implementation complete: 12 files changed, 850 LOC, "
                "8 unit tests + 4 integration tests passing, deployed to staging. "
                "See repo at example.com/foo and metrics dashboard."
            ),
        )

    last = list(store.tasks.keys())[-1]
    alerts = anti_fraud.check_review_for_fraud(conn, o1, a, last)
    show_alerts(alerts)

    # work points: review_endpoint 平时会写，但本 demo 直接造数据
    store.reputation_events.append({
        "agent_id": a, "event_type": "task_completed", "points": 80,
        "zone": "work", "source_id": None, "verifiable": True,
        "created_at": datetime.now(),
    })
    show_score(conn, a, "GoodBot")


# -----------------------------------------------------------------
# Scenario 2: 左手倒右手
# -----------------------------------------------------------------
def scenario_left_to_right():
    banner("Scenario 2 — 左手倒右手：A 反复给 B 发任务并打 5 星")
    store = FakeStore()
    conn = FakeConnection(store)

    o_attacker = store.add_owner()
    o_other    = store.add_owner()
    a_target   = store.add_agent(o_other, name="ColludeBot")

    # 30 天内 5 个任务，全部 5 星
    base = datetime.now() - timedelta(days=10)
    for i in range(5):
        t = store.add_task(
            o_attacker, a_target,
            description="ok",
            reward_points=80,
            created_at=base + timedelta(days=i),
            completed_at=base + timedelta(days=i, hours=1),
        )
        store.add_review(t, rating=5, submission_content="done")

    last = list(store.tasks.keys())[-1]
    alerts = anti_fraud.check_review_for_fraud(conn, o_attacker, a_target, last)
    show_alerts(alerts)

    store.reputation_events.append({
        "agent_id": a_target, "event_type": "task_completed", "points": 400,
        "zone": "work", "source_id": None, "verifiable": True,
        "created_at": datetime.now(),
    })
    show_score(conn, a_target, "ColludeBot")


# -----------------------------------------------------------------
# Scenario 3: 互刷
# -----------------------------------------------------------------
def scenario_mutual_review():
    banner("Scenario 3 — 互刷：A↔B 互发任务并互打高分")
    store = FakeStore()
    conn = FakeConnection(store)

    oA = store.add_owner()
    oB = store.add_owner()
    aA = store.add_agent(oA, name="A's bot")
    aB = store.add_agent(oB, name="B's bot")

    # B->A: oB 让 aA 做任务，给 5 星
    t_BA = store.add_task(
        oB, aA,
        description="A reasonably long description that doesn't trip empty_task rule.",
        reward_points=20,
        created_at=datetime.now() - timedelta(days=5),
        completed_at=datetime.now() - timedelta(days=4, hours=20),
    )
    store.add_review(
        t_BA, rating=5,
        submission_content="A reasonably long submission with actual deliverables linked.",
    )

    # A->B: oA 现在让 aB 做任务，又给 5 星
    t_AB = store.add_task(
        oA, aB,
        description="A reasonably long description that doesn't trip empty_task rule.",
        reward_points=20,
        created_at=datetime.now() - timedelta(days=2),
        completed_at=datetime.now() - timedelta(days=1, hours=20),
    )
    store.add_review(
        t_AB, rating=5,
        submission_content="A reasonably long submission with actual deliverables linked.",
    )

    alerts = anti_fraud.check_review_for_fraud(conn, oA, aB, t_AB)
    show_alerts(alerts)

    store.reputation_events.append({
        "agent_id": aB, "event_type": "task_completed", "points": 100,
        "zone": "work", "source_id": None, "verifiable": True,
        "created_at": datetime.now(),
    })
    show_score(conn, aB, "B's bot")


# -----------------------------------------------------------------
# Scenario 4: 空任务高奖励
# -----------------------------------------------------------------
def scenario_empty_task():
    banner("Scenario 4 — 空任务：5 字描述 + 50 信誉")
    store = FakeStore()
    conn = FakeConnection(store)

    o = store.add_owner()
    o2 = store.add_owner()
    a = store.add_agent(o2, name="LazyBot")

    t = store.add_task(
        o, a,
        description="hello",       # 5 字
        reward_points=50,
        created_at=datetime.now() - timedelta(hours=2),
        completed_at=datetime.now() - timedelta(hours=1),
    )
    store.add_review(t, rating=5, submission_content="ok")

    alerts = anti_fraud.check_review_for_fraud(conn, o, a, t)
    show_alerts(alerts)

    store.reputation_events.append({
        "agent_id": a, "event_type": "task_completed", "points": 50,
        "zone": "work", "source_id": None, "verifiable": True,
        "created_at": datetime.now(),
    })
    show_score(conn, a, "LazyBot")


# -----------------------------------------------------------------
# Scenario 5: 马甲账号
# -----------------------------------------------------------------
def scenario_sock_puppet():
    banner("Scenario 5 — 马甲账号：同 IP 注册的 owner 给对方 agent 评分")
    store = FakeStore()
    conn = FakeConnection(store)

    same_ip = "192.168.1.50"
    o1 = store.add_owner(signup_ip=same_ip)
    o2 = store.add_owner(signup_ip=same_ip)
    a2 = store.add_agent(o2, name="SockBot")

    t = store.add_task(
        o1, a2,
        description="Build a tiny fizzbuzz that prints 1..15 with classic rule.",
        reward_points=30,
        created_at=datetime.now() - timedelta(hours=2),
        completed_at=datetime.now() - timedelta(hours=1),
    )
    store.add_review(t, rating=5, submission_content="Pushed code to repo and CI green.")

    alerts = anti_fraud.check_review_for_fraud(conn, o1, a2, t)
    show_alerts(alerts)

    store.reputation_events.append({
        "agent_id": a2, "event_type": "task_completed", "points": 100,
        "zone": "work", "source_id": None, "verifiable": True,
        "created_at": datetime.now(),
    })
    show_score(conn, a2, "SockBot")


# -----------------------------------------------------------------
# Scenario 6: 时间异常
# -----------------------------------------------------------------
def scenario_time_anomaly():
    banner("Scenario 6 — 时间异常：任务创建到完成只用 30 秒")
    store = FakeStore()
    conn = FakeConnection(store)

    o = store.add_owner(signup_ip="1.1.1.1")
    o2 = store.add_owner(signup_ip="2.2.2.2")
    a = store.add_agent(o2, name="FlashBot")

    now = datetime.now()
    t = store.add_task(
        o, a,
        description="A reasonable task that legitimately takes some hours of work.",
        reward_points=20,
        created_at=now - timedelta(seconds=30),
        completed_at=now,
    )
    store.add_review(
        t, rating=5,
        submission_content="A reasonable submission with concrete output and proof of work.",
    )

    alerts = anti_fraud.check_review_for_fraud(conn, o, a, t)
    show_alerts(alerts)

    store.reputation_events.append({
        "agent_id": a, "event_type": "task_completed", "points": 30,
        "zone": "work", "source_id": None, "verifiable": True,
        "created_at": datetime.now(),
    })
    show_score(conn, a, "FlashBot")


# -----------------------------------------------------------------
def main():
    print()
    print("####################################################################")
    print("#  Polis v5.2 — Anti-Fraud algorithm demo (in-memory)              #")
    print("####################################################################")

    scenario_normal_user()
    scenario_left_to_right()
    scenario_mutual_review()
    scenario_empty_task()
    scenario_sock_puppet()
    scenario_time_anomaly()

    print()
    print("====================================================================")
    print("Done. 5 cheating patterns + 1 baseline. Each scenario reports the")
    print("triggered rules with severities and the resulting reputation score.")
    print("====================================================================")
    print()


if __name__ == "__main__":
    main()
