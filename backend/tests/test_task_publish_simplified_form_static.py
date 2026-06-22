from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "frontend"


def test_task_publish_form_is_simplified_and_supports_local_file_selection():
    page = (FRONTEND / "app/tasks/new/page.tsx").read_text()

    kept_labels = [
        "标题 *",
        "描述 *",
        "预算（Credits，可选）",
        "截止时间（可选）",
        "优先级",
        "附件（可选）",
    ]
    for label in kept_labels:
        assert label in page

    assert 'type="file"' in page
    assert "selectedFiles" in page
    assert "removeSelectedFile" in page
    assert "已选择" in page

    removed_complex_fields = [
        "Required Skills",
        "required_capabilities",
        "期望输出格式",
        "deliverable_type",
        "指定 Agent",
        "assigned_agent_id",
        "estimated_hours",
    ]
    for field in removed_complex_fields:
        assert field not in page


def test_task_publish_success_refreshes_marketplace_and_redirects_after_delay():
    page = (FRONTEND / "app/tasks/new/page.tsx").read_text()

    assert "useQueryClient" in page
    assert "useRouter" in page
    assert "queryClient.invalidateQueries({ queryKey: ['tasks'] })" in page
    assert "setTimeout(() => {" in page
    assert "router.push('/tasks')" in page
    assert "2000" in page
