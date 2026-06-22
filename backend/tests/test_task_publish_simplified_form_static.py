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


def test_task_publish_sends_selected_files_as_attachments():
    page = (FRONTEND / "app/tasks/new/page.tsx").read_text()
    types = (FRONTEND / "lib/api/types.ts").read_text()

    assert "readFileAsBase64" in page
    assert "Promise.all(selectedFiles.map" in page
    assert "content_base64" in page
    assert "attachments" in page
    assert "attachments?:" in types


def test_task_detail_supports_user_owned_agent_claim_and_task_attachments():
    page = (FRONTEND / "app/tasks/[id]/page.tsx").read_text()
    api = (FRONTEND / "lib/api/tasks.ts").read_text()

    assert "agentsApi.listMine" in page
    assert "effectiveAgentId" in page
    assert "tasksApi.claim(taskId, effectiveAgentId" in page
    assert "任务附件" in page
    assert "task.attachments" in page
    assert "`/messages/${task.owner_id}`" in page
    assert "claim: async (id: string, agentId?: string)" in api
