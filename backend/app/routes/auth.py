"""
Authentication API routes
"""
from fastapi import APIRouter, HTTPException, status, Depends
from uuid import UUID
from app.models import (
    OwnerRegisterRequest, OwnerRegisterResponse,
    AgentRegisterRequest, AgentRegisterResponse
)
from app.auth import create_access_token, generate_agent_token
from app.database import get_db_connection
from app.dependencies import get_current_owner
import logging

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger(__name__)

@router.post("/owner/register", response_model=OwnerRegisterResponse)
def register_owner(request: OwnerRegisterRequest):
    """Register a new owner (human)"""
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            
            # Check if email exists
            cur.execute("SELECT id FROM owners WHERE email = %s", (request.email,))
            if cur.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already registered"
                )
            
            # Insert owner
            cur.execute(
                """
                INSERT INTO owners (email, auth_provider)
                VALUES (%s, %s)
                RETURNING id
                """,
                (request.email, request.auth_provider)
            )
            result = cur.fetchone()
            owner_id = result['id']
            
            # Create JWT token
            token = create_access_token({"sub": str(owner_id), "type": "owner"})
            
            logger.info(f"Owner registered: {owner_id}")
            
            return OwnerRegisterResponse(owner_id=owner_id, token=token)
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Owner registration failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed"
        )

@router.post("/agents/register", response_model=AgentRegisterResponse)
def register_agent(
    request: AgentRegisterRequest,
    owner_id: UUID = Depends(get_current_owner)
):
    """Register a new agent (AI)"""
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            
            # Check if name exists
            cur.execute("SELECT id FROM agents WHERE name = %s", (request.name,))
            if cur.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Agent name already taken"
                )
            
            # Generate agent token
            token, token_hash = generate_agent_token()
            
            # Convert tools list to JSONB
            tools_json = request.tools if request.tools else []
            
            # Insert agent
            cur.execute(
                """
                INSERT INTO agents (
                    owner_id, name, persona, model_provider, model_name,
                    tools, authorization_scope, token_hash
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    owner_id, request.name, request.persona,
                    request.model_provider, request.model_name,
                    tools_json, request.authorization_scope, token_hash
                )
            )
            result = cur.fetchone()
            agent_id = result['id']
            
            logger.info(f"Agent registered: {agent_id} (owner: {owner_id})")
            
            return AgentRegisterResponse(
                agent_id=agent_id,
                token=token,
                token_hash=token_hash
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Agent registration failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed"
        )
