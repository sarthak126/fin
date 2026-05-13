"""
Python enums used by Pydantic schemas. 
The database models are now handled entirely by Prisma Client Python,
so we just need to preserve these enums for type safety in our API layer.
"""

import enum

class UserRole(str, enum.Enum):
    ADMIN = "admin"
    ANALYST = "analyst"
    VIEWER = "viewer"

class DocumentStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    ANALYZED = "analyzed"
    FAILED = "failed"

class CaseStatus(str, enum.Enum):
    DRAFT = "draft"
    COLLECTING = "collecting"
    FINALIZED = "finalized"

class DocumentType(str, enum.Enum):
    BANK_STATEMENT = "bank_statement"
    TAX_RETURN = "tax_return"
    SALARY_SLIP = "salary_slip"
    EMPLOYMENT_LETTER = "employment_letter"
    INCOME_PROOF = "income_proof"
    ID_DOCUMENT = "id_document"
    OTHER = "other"

class Recommendation(str, enum.Enum):
    APPROVE = "approve"
    REVIEW = "review"
    REJECT = "reject"


class DecisionStatus(str, enum.Enum):
    APPROVE = "approve"
    MANUAL_REVIEW = "manual_review"
    REJECT = "reject"
    INSUFFICIENT_HISTORY = "insufficient_history"
