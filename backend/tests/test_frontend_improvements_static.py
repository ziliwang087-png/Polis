from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "frontend"


def test_navigation_dashboard_and_install_copy_explain_task_marketplace():
    navbar = (FRONTEND / "components/Navbar.tsx").read_text()
    dashboard = (FRONTEND / "app/me/page.tsx").read_text()
    install = (FRONTEND / "app/agents/[id]/install/page.tsx").read_text()

    assert "/tasks" in navbar
    assert "任务广场" in navbar
    assert "/tasks/new" in navbar
    assert "发任务" in navbar

    assert "信誉分（XP/等级）" in dashboard
    assert "影响任务推荐排序" in dashboard
    assert "Credit 余额" in dashboard
    assert "发布带预算的任务会预扣 Credit" in dashboard
    assert "任务验收后支付给完成任务的 Agent owner" in dashboard
    assert 'href="/tasks/new"' in dashboard
    assert 'href="/jobs/new"' not in dashboard

    assert "/api/v1/tasks/pending" in install
    assert "Agent 自己判断" in install
    assert "轮询" in install


def test_auth_store_hydrates_after_mount_to_avoid_localstorage_mismatch():
    store = (FRONTEND / "lib/store.ts").read_text()
    providers = (FRONTEND / "app/providers.tsx").read_text()

    assert "hasHydrated" in store
    assert "hydrateFromStorage" in store
    assert "token: null" in store
    assert "typeof window !== 'undefined' ? localStorage.getItem" not in store
    assert "hydrateFromStorage()" in providers
