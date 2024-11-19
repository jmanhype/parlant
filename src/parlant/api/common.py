from enum import Enum
from typing import Any, Mapping, Optional, TypeAlias, cast

from parlant.core.common import DefaultBaseModel
from parlant.core.guideline_connections import ConnectionKind
from parlant.core.guidelines import GuidelineId


def apigen_config(group_name: str, method_name: str) -> Mapping[str, Any]:
    return {
        "openapi_extra": {
            "x-fern-sdk-group-name": group_name,
            "x-fern-sdk-method-name": method_name,
        }
    }


class EvaluationStatusDTO(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ConnectionKindDTO(Enum):
    ENTAILS = "entails"
    SUGGESTS = "suggests"


class GuidelineContentDTO(DefaultBaseModel):
    condition: str
    action: str


class GuidelinePayloadOperationDTO(Enum):
    ADD = "add"
    UPDATE = "update"


class CoherenceCheckKindDTO(Enum):
    CONTRADICTION_WITH_EXISTING_GUIDELINE = "contradiction_with_existing_guideline"
    CONTRADICTION_WITH_ANOTHER_EVALUATED_GUIDELINE = (
        "contradiction_with_another_evaluated_guideline"
    )


class ConnectionPropositionKindDTO(Enum):
    CONNECTION_WITH_EXISTING_GUIDELINE = "connection_with_existing_guideline"
    CONNECTION_WITH_ANOTHER_EVALUATED_GUIDELINE = "connection_with_another_evaluated_guideline"


class PayloadKindDTO(Enum):
    GUIDELINE = "guideline"


class GuidelinePayloadDTO(DefaultBaseModel):
    content: GuidelineContentDTO
    operation: GuidelinePayloadOperationDTO
    updated_id: Optional[GuidelineId] = None
    coherence_check: bool
    connection_proposition: bool


class PayloadDTO(DefaultBaseModel):
    kind: PayloadKindDTO
    guideline: Optional[GuidelinePayloadDTO]


class CoherenceCheckDTO(DefaultBaseModel):
    kind: CoherenceCheckKindDTO
    first: GuidelineContentDTO
    second: GuidelineContentDTO
    issue: str
    severity: int


class ConnectionPropositionDTO(DefaultBaseModel):
    check_kind: ConnectionPropositionKindDTO
    source: GuidelineContentDTO
    target: GuidelineContentDTO
    connection_kind: ConnectionKindDTO


class GuidelineInvoiceDataDTO(DefaultBaseModel):
    coherence_checks: list[CoherenceCheckDTO]
    connection_propositions: Optional[list[ConnectionPropositionDTO]]


class InvoiceDataDTO(DefaultBaseModel):
    guideline: Optional[GuidelineInvoiceDataDTO]


def connection_kind_to_dto(kind: ConnectionKind) -> ConnectionKindDTO:
    return cast(
        ConnectionKindDTO,
        {
            ConnectionKind.ENTAILS: "entails",
            ConnectionKind.SUGGESTS: "suggests",
        }[kind],
    )


def connection_kind_dto_to_connection_kind(dto: ConnectionKindDTO) -> ConnectionKind:
    return {
        ConnectionKindDTO.ENTAILS: ConnectionKind.ENTAILS,
        ConnectionKindDTO.SUGGESTS: ConnectionKind.SUGGESTS,
    }[dto]


class ToolIdDTO(DefaultBaseModel):
    service_name: str
    tool_name: str


JSONSerializableDTO: TypeAlias = Any
