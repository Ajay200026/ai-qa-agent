import re

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.workflow_repository import WorkflowRepository

TEMPLATE_KEYWORDS: dict[str, list[str]] = {
    "DATA_CHANGE_REQUEST": ["data change", "primary group", "tc_dc", "sales office"],
    "NEW_FSV_CUSTOMER": ["fsv customer", "new fsv"],
    "NEW_DSD_CUSTOMER": ["dsd customer", "new dsd"],
    "NEW_CUSTOMER_REQUEST": ["new customer"],
    "ACCOUNT_RECEIVABLE": ["account receivable", "new payer", "payer"],
    "CONTACT_UPDATE": ["contact update", "suppression", "unsuppression"],
}


class TemplateMatcher:
    def __init__(self, db: AsyncSession | None = None):
        self.db = db

    async def match(self, text: str, explicit_key: str | None = None) -> str:
        if explicit_key:
            return explicit_key

        explicit = re.search(
            r"template\s*[=:]\s*([A-Z_]+)",
            text,
            re.IGNORECASE,
        )
        if explicit:
            return explicit.group(1).upper()

        lower = text.lower()
        best_key = "DATA_CHANGE_REQUEST"
        best_score = 0
        for key, keywords in TEMPLATE_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in lower)
            if score > best_score:
                best_score = score
                best_key = key

        if self.db:
            repo = WorkflowRepository(self.db)
            template = await repo.get_by_key(best_key)
            if not template:
                active = await repo.list_active()
                if active:
                    return active[0].key
        return best_key
