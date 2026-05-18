from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.db.base import Base
from app.db.session import get_db
from app.main import create_app
from app.models import (
    Customer,
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeDocumentPermission,
    KnowledgeDocumentVersion,
    KnowledgeSourceFile,
    KnowledgeSourceFilePermission,
    Project,
    User,
    UserChannelBinding,
)


def make_client() -> tuple[TestClient, Session]:
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine)
    db = TestingSessionLocal()
    app = create_app()

    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app), db


def auth_headers(user_id: str) -> dict[str, str]:
    settings = get_settings()
    headers = {"x-actor-internal-user-id": user_id}
    if settings.agent_tool_api_key:
        headers["authorization"] = f"Bearer {settings.agent_tool_api_key}"
    return headers


def agent_tool_headers() -> dict[str, str]:
    settings = get_settings()
    return {"authorization": f"Bearer {settings.agent_tool_api_key}"} if settings.agent_tool_api_key else {}


def test_agent_project_search_filters_to_actor_accessible_projects():
    client, db = make_client()
    db.add_all(
        [
            User(id="owner", name="负责人", role="member", status="active", knowledge_access_policy="own"),
            User(id="outsider", name="外部账号", role="member", status="active", knowledge_access_policy="own"),
            Customer(id="customer-1", name="客户A", owner_user_id="owner"),
            Project(id="project-private", customer_id="customer-1", name="私有项目", owner_user_id="owner"),
        ]
    )
    db.commit()

    response = client.post(
        "/api/agent-tools/project_search",
        json={
            "actor": {"channel": "web", "external_user_id": "outsider", "internal_user_id": "outsider"},
            "input": {"query": "私有"},
        },
        headers=agent_tool_headers(),
    )

    assert response.status_code == 200
    assert response.json()["data"]["projects"] == []


def test_agent_project_get_brief_denies_inaccessible_project():
    client, db = make_client()
    db.add_all(
        [
            User(id="owner", name="负责人", role="member", status="active", knowledge_access_policy="own"),
            User(id="outsider", name="外部账号", role="member", status="active", knowledge_access_policy="own"),
            Customer(id="customer-1", name="客户A", owner_user_id="owner"),
            Project(id="project-private", customer_id="customer-1", name="私有项目", owner_user_id="owner"),
        ]
    )
    db.commit()

    response = client.post(
        "/api/agent-tools/project_get_brief",
        json={
            "actor": {"channel": "web", "external_user_id": "outsider", "internal_user_id": "outsider"},
            "input": {"project_id": "project-private"},
        },
        headers=agent_tool_headers(),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert body["error_code"] == "PERMISSION_DENIED"


def test_agent_kb_search_rejects_unknown_actor():
    client, db = make_client()
    db.add_all(
        [
            User(id="fallback", name="本地 fallback", role="member", status="active", knowledge_access_policy="all"),
            UserChannelBinding(user_id="fallback", channel="openclaw", external_user_id="unknown"),
            KnowledgeDocument(
                id="doc-private",
                title="私有知识",
                source_type="manual",
                content_text="只有已识别账号可以查询。",
                created_by="owner",
            ),
        ]
    )
    db.commit()

    response = client.post(
        "/api/agent-tools/kb_search",
        json={
            "actor": {"channel": "web", "external_user_id": "missing-user"},
            "input": {"query": "私有知识"},
        },
        headers=agent_tool_headers(),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert body["error_code"] == "UNAUTHORIZED"


def test_agent_kb_search_includes_source_file_and_version_metadata():
    client, db = make_client()
    db.add_all(
        [
            User(id="owner", name="知识用户", role="member", status="active", knowledge_access_policy="all"),
            KnowledgeDocument(
                id="doc-versioned",
                title="版本化售后政策",
                source_type="file_upload",
                source_file_name="售后政策.pdf",
                source_file_path="/tmp/售后政策.pdf",
                content_text="七天内可以退货。",
                created_by="owner",
                current_version=3,
            ),
            KnowledgeChunk(
                document_id="doc-versioned",
                chunk_index=0,
                content_text="七天内可以退货。",
            ),
        ]
    )
    db.commit()

    response = client.post(
        "/api/agent-tools/kb_search",
        json={
            "actor": {"channel": "web", "external_user_id": "owner", "internal_user_id": "owner"},
            "input": {"query": "几天内可以退货"},
        },
        headers=agent_tool_headers(),
    )

    assert response.status_code == 200
    match = response.json()["data"]["matches"][0]
    assert match["document_version"] == 3
    assert match["source_file_name"] == "售后政策.pdf"
    assert match["source_file_path"] == "/tmp/售后政策.pdf"


def test_management_endpoint_rejects_non_admin_actor():
    client, db = make_client()
    db.add_all(
        [
            User(id="admin", name="管理员", role="admin", status="active", knowledge_access_policy="all"),
            User(id="member", name="普通用户", role="member", status="active", knowledge_access_policy="own"),
        ]
    )
    db.commit()

    response = client.post(
        "/api/database/users/member/knowledge-policy",
        json={"knowledge_access_policy": "all"},
        headers=auth_headers("member"),
    )

    assert response.status_code == 403


def test_management_endpoint_allows_admin_actor():
    client, db = make_client()
    db.add_all(
        [
            User(id="admin", name="管理员", role="admin", status="active", knowledge_access_policy="all"),
            User(id="member", name="普通用户", role="member", status="active", knowledge_access_policy="own"),
        ]
    )
    db.commit()

    response = client.post(
        "/api/database/users/member/knowledge-policy",
        json={"knowledge_access_policy": "all"},
        headers=auth_headers("admin"),
    )

    assert response.status_code == 200
    assert db.get(User, "member").knowledge_access_policy == "all"


def test_management_can_publish_pending_document():
    client, db = make_client()
    db.add_all(
        [
            User(id="admin", name="管理员", role="admin", status="active", knowledge_access_policy="all"),
            KnowledgeDocument(
                id="doc-pending",
                title="待审核退货规则",
                source_type="file_upload",
                content_text="商品签收七天内可以退货。",
                created_by="member",
                review_status="pending_review",
                publication_status="draft",
                index_status="pending_review",
            ),
        ]
    )
    db.commit()

    response = client.post("/api/database/knowledge/doc-pending/publish", headers=auth_headers("admin"))

    assert response.status_code == 200
    body = response.json()
    document = db.get(KnowledgeDocument, "doc-pending")
    assert body["document"]["review_status"] == "approved"
    assert body["document"]["publication_status"] == "published"
    assert body["version"]["version_number"] == 1
    assert document is not None
    assert document.reviewed_by == "admin"
    assert db.query(KnowledgeDocumentVersion).filter_by(document_id="doc-pending").count() == 1
    assert db.query(KnowledgeChunk).filter_by(document_id="doc-pending").count() > 0


def test_source_file_download_respects_permissions(tmp_path):
    client, db = make_client()
    source_path = tmp_path / "source.pdf"
    source_path.write_bytes(b"original pdf bytes")
    db.add_all(
        [
            User(id="owner", name="上传人", role="member", status="active", knowledge_access_policy="own"),
            User(id="outsider", name="外部账号", role="member", status="active", knowledge_access_policy="own"),
            KnowledgeSourceFile(
                id="file-1",
                file_name="source.pdf",
                file_path=str(source_path),
                uploaded_by="owner",
                parse_status="parsed",
            ),
        ]
    )
    db.commit()

    denied = client.get("/api/database/source-files/file-1/download", headers=auth_headers("outsider"))
    allowed = client.get("/api/database/source-files/file-1/download", headers=auth_headers("owner"))

    assert denied.status_code == 403
    assert allowed.status_code == 200
    assert allowed.content == b"original pdf bytes"


def test_management_endpoint_syncs_channel_accounts_as_private_users():
    client, db = make_client()
    db.add(User(id="admin", name="管理员", role="admin", status="active", knowledge_access_policy="all"))
    db.commit()

    response = client.post(
        "/api/database/users/channel-accounts/sync",
        json={"channel": "openclaw-weixin", "account_ids": ["6bbfb1c838b3-im-bot", "b8230f0855ca-im-bot"]},
        headers=auth_headers("admin"),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["synced_count"] == 2
    first = db.get(User, "6bbfb1c838b3-im-bot")
    second = db.get(User, "b8230f0855ca-im-bot")
    assert first is not None
    assert second is not None
    assert first.knowledge_access_policy == "own"
    assert second.knowledge_access_policy == "own"
    first_binding = db.query(UserChannelBinding).filter_by(channel="openclaw-weixin", external_user_id="6bbfb1c838b3-im-bot").one()
    assert first_binding.user_id == "6bbfb1c838b3-im-bot"


def test_management_endpoint_syncs_channel_account_with_business_alias():
    client, db = make_client()
    db.add(User(id="admin", name="管理员", role="admin", status="active", knowledge_access_policy="all"))
    db.commit()

    response = client.post(
        "/api/database/users/channel-accounts/sync",
        json={"channel": "openclaw-weixin", "accounts": [{"account_id": "3f81836398cd-im-bot", "user_id": "wx-wangsuzhen"}]},
        headers=auth_headers("admin"),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["synced_users"][0]["id"] == "wx-wangsuzhen"
    user = db.get(User, "wx-wangsuzhen")
    assert user is not None
    assert user.name == "openclaw-weixin:wx-wangsuzhen"
    binding = db.query(UserChannelBinding).filter_by(channel="openclaw-weixin", external_user_id="3f81836398cd-im-bot").one()
    assert binding.user_id == "wx-wangsuzhen"


def test_management_endpoint_renames_existing_channel_account_user_to_business_alias():
    client, db = make_client()
    db.add_all(
        [
            User(id="admin", name="管理员", role="admin", status="active", knowledge_access_policy="all"),
            User(id="3f81836398cd-im-bot", name="openclaw-weixin:3f81836398cd-im-bot", role="member", status="active", knowledge_access_policy="own"),
            UserChannelBinding(user_id="3f81836398cd-im-bot", channel="openclaw-weixin", external_user_id="3f81836398cd-im-bot"),
            KnowledgeDocument(id="doc-1", title="原账号知识", source_type="manual", content_text="原账号上传的知识。", created_by="3f81836398cd-im-bot"),
        ]
    )
    db.commit()

    response = client.post(
        "/api/database/users/channel-accounts/sync",
        json={"channel": "openclaw-weixin", "accounts": [{"account_id": "3f81836398cd-im-bot", "user_id": "wx-wangsuzhen"}]},
        headers=auth_headers("admin"),
    )

    assert response.status_code == 200
    assert db.get(User, "3f81836398cd-im-bot") is None
    user = db.get(User, "wx-wangsuzhen")
    assert user is not None
    assert user.name == "openclaw-weixin:wx-wangsuzhen"
    binding = db.query(UserChannelBinding).filter_by(channel="openclaw-weixin", external_user_id="3f81836398cd-im-bot").one()
    document = db.get(KnowledgeDocument, "doc-1")
    assert binding.user_id == "wx-wangsuzhen"
    assert document is not None
    assert document.created_by == "wx-wangsuzhen"


def test_channel_account_alias_merge_deduplicates_existing_permissions():
    client, db = make_client()
    db.add_all(
        [
            User(id="admin", name="管理员", role="admin", status="active", knowledge_access_policy="all"),
            User(id="wx-wangsuzhen", name="openclaw-weixin:wx-wangsuzhen", role="member", status="active", knowledge_access_policy="own"),
            User(id="3f81836398cd-im-bot", name="openclaw-weixin:3f81836398cd-im-bot", role="member", status="active", knowledge_access_policy="own"),
            UserChannelBinding(user_id="3f81836398cd-im-bot", channel="openclaw-weixin", external_user_id="3f81836398cd-im-bot"),
            KnowledgeDocument(id="doc-1", title="授权知识", source_type="manual", content_text="权限去重。", created_by="admin"),
            KnowledgeDocumentPermission(document_id="doc-1", user_id="wx-wangsuzhen", access_level="read"),
            KnowledgeDocumentPermission(document_id="doc-1", user_id="3f81836398cd-im-bot", access_level="read"),
            KnowledgeSourceFile(id="file-1", file_name="source.pdf", file_path="/tmp/source.pdf", uploaded_by="admin"),
            KnowledgeSourceFilePermission(source_file_id="file-1", user_id="wx-wangsuzhen", access_level="read"),
            KnowledgeSourceFilePermission(source_file_id="file-1", user_id="3f81836398cd-im-bot", access_level="read"),
        ]
    )
    db.commit()

    response = client.post(
        "/api/database/users/channel-accounts/sync",
        json={"channel": "openclaw-weixin", "accounts": [{"account_id": "3f81836398cd-im-bot", "user_id": "wx-wangsuzhen"}]},
        headers=auth_headers("admin"),
    )

    assert response.status_code == 200
    assert db.get(User, "3f81836398cd-im-bot") is None
    assert db.query(KnowledgeDocumentPermission).filter_by(document_id="doc-1", user_id="wx-wangsuzhen").count() == 1
    assert db.query(KnowledgeSourceFilePermission).filter_by(source_file_id="file-1", user_id="wx-wangsuzhen").count() == 1


def test_channel_account_alias_sync_reports_invalid_alias_reason():
    client, db = make_client()
    db.add(User(id="admin", name="管理员", role="admin", status="active", knowledge_access_policy="all"))
    db.commit()

    response = client.post(
        "/api/database/users/channel-accounts/sync",
        json={"channel": "openclaw-weixin", "accounts": [{"account_id": "3f81836398cd-im-bot", "user_id": "微信用户"}]},
        headers=auth_headers("admin"),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["synced_count"] == 0
    assert body["skipped_account_ids"] == ["3f81836398cd-im-bot"]
    assert body["skipped_accounts"][0]["reason"].startswith("user_id must be")


def test_management_endpoint_rejects_channel_account_sync_for_non_admin_actor():
    client, db = make_client()
    db.add_all(
        [
            User(id="admin", name="管理员", role="admin", status="active", knowledge_access_policy="all"),
            User(id="member", name="普通用户", role="member", status="active", knowledge_access_policy="own"),
        ]
    )
    db.commit()

    response = client.post(
        "/api/database/users/channel-accounts/sync",
        json={"channel": "openclaw-weixin", "account_ids": ["6bbfb1c838b3-im-bot"]},
        headers=auth_headers("member"),
    )

    assert response.status_code == 403
    assert db.get(User, "6bbfb1c838b3-im-bot") is None


def test_management_endpoint_rejects_unknown_actor():
    client, db = make_client()
    db.add(User(id="member", name="普通用户", role="member", status="active", knowledge_access_policy="own"))
    db.commit()

    response = client.post(
        "/api/database/users/member/knowledge-policy",
        json={"knowledge_access_policy": "all"},
        headers=auth_headers("missing"),
    )

    assert response.status_code == 401
