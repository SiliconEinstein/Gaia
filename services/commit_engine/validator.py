# services/commit_engine/validator.py
from libs.models import AddEdgeOp, ModifyEdgeOp, ModifyNodeOp, ValidationResult


class Validator:
    async def validate(self, operations: list) -> list[ValidationResult]:
        """Structural validation of each operation. Returns one ValidationResult per operation."""
        results = []
        for i, op in enumerate(operations):
            errors = []
            if isinstance(op, AddEdgeOp):
                if not op.premises:
                    errors.append("premises must not be empty")
                if not op.conclusions:
                    errors.append("conclusions must not be empty")
                if not op.type:
                    errors.append("type must not be empty")
                if not op.reasoning:
                    errors.append("reasoning must not be empty")
            elif isinstance(op, ModifyEdgeOp):
                if not op.changes:
                    errors.append("changes must not be empty")
            elif isinstance(op, ModifyNodeOp):
                if not op.changes:
                    errors.append("changes must not be empty")
            else:
                errors.append(f"unknown operation type: {type(op).__name__}")
            results.append(ValidationResult(op_index=i, valid=len(errors) == 0, errors=errors))
        return results
