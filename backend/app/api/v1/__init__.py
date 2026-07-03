from fastapi import APIRouter

from app.api.v1 import (
    account_queries,
    auth,
    executions,
    knowledge,
    knowledge_engine,
    login_as_profiles,
    projects,
    reports,
    salesforce,
    scenarios,
    system,
    workflows,
)

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(projects.router, prefix="/projects", tags=["projects"])
api_router.include_router(
    account_queries.router, prefix="/account-queries", tags=["account-queries"]
)
api_router.include_router(
    login_as_profiles.router, prefix="/login-as-profiles", tags=["login-as-profiles"]
)
api_router.include_router(salesforce.router, prefix="/salesforce", tags=["salesforce"])
api_router.include_router(scenarios.router, prefix="/scenarios", tags=["scenarios"])
api_router.include_router(workflows.router, prefix="/workflows", tags=["workflows"])
api_router.include_router(executions.router, prefix="/executions", tags=["executions"])
api_router.include_router(reports.router, prefix="/reports", tags=["reports"])
api_router.include_router(knowledge.router, prefix="/knowledge", tags=["knowledge"])
api_router.include_router(
    knowledge_engine.router, prefix="/knowledge", tags=["knowledge-engine"]
)
api_router.include_router(system.router, tags=["system"])
