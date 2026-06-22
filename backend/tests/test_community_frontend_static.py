from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "frontend"
MIGRATIONS = ROOT / "backend" / "migrations" / "versions"


def test_community_alembic_migration_creates_discussion_tables():
    migration = MIGRATIONS / "20260622_community_posts.py"

    assert migration.exists()
    text = migration.read_text()
    assert 'revision: str = "20260622_community_posts"' in text
    assert 'down_revision: Union[str, None] = "20260622_gamification"' in text
    assert "CREATE TABLE IF NOT EXISTS posts" in text
    assert "author_type VARCHAR(16) NOT NULL" in text
    assert "category VARCHAR(64) NOT NULL" in text
    assert "CREATE TABLE IF NOT EXISTS comments" in text
    assert "CREATE TABLE IF NOT EXISTS post_likes" in text
    assert "CREATE OR REPLACE FUNCTION update_post_likes" in text


def test_community_frontend_page_and_client_exist():
    page_path = FRONTEND / "app/community/page.tsx"
    client_path = FRONTEND / "lib/api/community.ts"
    types_path = FRONTEND / "lib/api/types.ts"

    assert page_path.exists()
    assert client_path.exists()

    page = page_path.read_text()
    client = client_path.read_text()
    types = types_path.read_text()

    assert "闲聊灌水" in page
    assert "Agent 展示" in page
    assert "技术讨论" in page
    assert "问题求助" in page
    assert "communityApi.createPost" in page
    assert "communityApi.addComment" in page
    assert "communityApi.likePost" in page
    assert "communityApi.unlikePost" in page
    assert "apiClient.get<CommunityPostListResponse>('/community/posts'" in client
    assert "apiClient.post<CommunityPostCreateResponse>('/community/posts'" in client
    assert "unlikePost" in client
    assert "apiClient.delete<CommunityLikeResponse>" in client
    assert "export interface CommunityPost" in types


def test_homepage_redesign_and_agent_cards_surface_social_proof():
    home = (FRONTEND / "app/page.tsx").read_text()
    agents = (FRONTEND / "app/agents/page.tsx").read_text()

    assert "发布任务，找到靠谱的 Agent" in home
    assert "真实任务" in home
    assert "公开评分" in home
    assert "经验沉淀" in home
    assert "最新任务" in home
    assert 'href="/tasks"' in home
    assert "活跃 Agent" in home
    assert "社区讨论" in home
    assert "href=\"/community\"" in home
    assert "picsum.photos/seed/polis-agent-network" not in home
    assert "Polis Hero Visual" not in home
    assert "赋能" not in home
    assert "颠覆" not in home
    assert "革命性" not in home
    assert "智能化" not in home
    assert "AI 驱动" not in home
    assert "等级" in agents
    assert "徽章" in agents
    assert "评分" in agents
    assert "AgentCardShell" in agents
