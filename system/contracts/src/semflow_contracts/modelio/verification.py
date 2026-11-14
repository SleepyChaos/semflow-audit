"""Algorithm extracted from app.contracts.verification.

Runtime dependencies are passed explicitly; no platform ORM or configuration.
Changes to JSON require checking the corresponding semflow_contracts/wire peer.
"""

"""Project-specific tests, with identical assertions before and after a patch."""
from pathlib import PurePosixPath
from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from semflow_contracts.modelio.stages import StrictModel


class VerificationCase(StrictModel):
    name: str = Field(pattern="^test_[A-Za-z0-9_]{1,100}$")
    category: Literal["security", "functional"]
    candidate_ids: list[UUID] = Field(default_factory=list, max_length=20)
    input_description: str = Field(min_length=2, max_length=800)
    expected_behavior: str = Field(min_length=2, max_length=1000)


class VerificationSuite(StrictModel):
    title: str = Field(min_length=2, max_length=160)
    summary: str = Field(min_length=10, max_length=1800)
    language: Literal["python", "javascript"]
    files: dict[str, str]
    cases: list[VerificationCase] = Field(min_length=2, max_length=30)
    assumptions: list[str] = Field(default_factory=list, max_length=12)

    @model_validator(mode="after")
    def scope(self):
        if not 1 <= len(self.files) <= 8 or sum(map(len, self.files.values())) > 50000:
            raise ValueError("测试文件数量或内容超过范围")
        for name in self.files:
            path = PurePosixPath(name)
            allowed = (
                name.startswith("test_") and path.suffix == ".py"
                if self.language == "python"
                else name.endswith((".test.cjs", ".test.mjs", ".test.js"))
            )
            if not allowed or len(path.parts) != 1 or "\\" in name or (":" in name):
                raise ValueError("测试只能保存在独立测试目录，不允许修改项目文件")
        names = [row.name for row in self.cases]
        if len(set(names)) != len(names):
            raise ValueError("测试名称必须唯一，不使用参数化子用例")
        if not any(row.category == "functional" for row in self.cases):
            raise ValueError("必须包含正常业务测试")
        security = [row for row in self.cases if row.category == "security"]
        if not security or any(not row.candidate_ids for row in security):
            raise ValueError("安全测试必须明确关联漏洞候选")
        # Interface peer: repair suite validation. Narrative language belongs to
        # presentation; AGENT: retain case/target/scope checks in both interfaces.
        return self


class SuiteGeneration(StrictModel):
    candidate_ids: list[UUID] = Field(min_length=1, max_length=20)
    image: str = Field(default="", max_length=200, pattern="^[A-Za-z0-9._/:@-]*$")
    requirements: str = Field(default="", max_length=4000)


class SuiteImport(StrictModel):
    suite: VerificationSuite
    image: str = Field(default="", max_length=200, pattern="^[A-Za-z0-9._/:@-]*$")


class VerificationRequest(StrictModel):
    suite_id: UUID
