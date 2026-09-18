from pydantic import BaseModel, Field
from typing import Optional

class ReviewerOutput(BaseModel):
    verdict: str = Field(description="PASS, FAIL, or INCONCLUSIVE")
    bug_resolved: bool = Field(description="True if the original bug is fixed, False otherwise")
    regression_detected: bool = Field(description="True if previously passing tests now fail, False otherwise")
    failure_category: Optional[str] = Field(description="Category of failure if applicable (e.g., WRONG_ROOT_CAUSE, INCOMPLETE_FIX, REGRESSION, TEST_FAILURE_UNRELATED, ENVIRONMENT_FAILURE, PATCH_APPLICATION_FAILURE, INSUFFICIENT_EVIDENCE, UNKNOWN)")
    summary: str = Field(description="A concise summary of the review")
    reason: str = Field(description="Detailed explanation of the verdict based on test evidence")
    confidence: float = Field(description="Confidence score between 0.0 and 1.0")
    recommended_action: str = Field(description="VERIFY_FULL_SUITE, REPLAN, STOP, or REQUEST_REVIEW")
