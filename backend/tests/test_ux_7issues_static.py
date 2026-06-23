from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "frontend"
BACKEND = ROOT / "backend"


def test_homepage_uses_light_surfaces_for_task_pool_and_reputation_cards():
    home = (FRONTEND / "app/page.tsx").read_text()

    assert "公开任务池" in home
    assert "从任务到信誉" in home
    assert "bg-[#101827]" not in home
    assert "border-slate-200 bg-white" in home
    assert "bg-[#f8fbff]" in home or "from-[#f8fbff]" in home


def test_leaderboard_uses_medal_icons_not_chinese_rank_words():
    page = (FRONTEND / "app/leaderboard/page.tsx").read_text()

    assert "🥇" in page
    assert "🥈" in page
    assert "🥉" in page
    assert "return '金'" not in page
    assert "return '银'" not in page
    assert "return '铜'" not in page


def test_agent_registration_redirects_to_install_flow_after_create():
    page = (FRONTEND / "app/agents/new/page.tsx").read_text()

    assert "useRouter" in page
    assert "router.push(`/agents/${data.id}/install`)" in page
    assert "拿到 demo_agent.py 模板" not in page
    assert "注册成功" not in page
    assert "复制命令" not in page


def test_install_page_clarifies_supported_llm_keys_without_jargon():
    page = (FRONTEND / "app/agents/[id]/install/page.tsx").read_text()

    expected = [
        "支持这些 key",
        "DeepSeek 官方",
        "OpenAI / GPT",
        "Claude",
        "通义千问",
        "月之暗面",
        "中转站",
    ]
    for text in expected:
        assert text in page
    assert "兼容 OpenAI SDK 的 endpoint" not in page


def test_upload_surfaces_local_fallback_and_plain_error_copy():
    storage = (BACKEND / "app/services/storage.py").read_text()
    task_page = (FRONTEND / "app/tasks/new/page.tsx").read_text()

    # 后端应该有本地 fallback 逻辑
    assert "LOCAL_UPLOAD_DIR" in storage
    assert "local_upload_url" in storage
    assert "_upload_local_bytes" in storage
    
    # 前端不应该有误导性错误提示（后端自动 fallback，用户无感知）
    assert "Supabase Storage is not configured" not in task_page
    assert "请重新发布一次" not in task_page
