"""Function declaration contract checks."""

from __future__ import annotations

import logging

from uptimely.spec import model as spec_model
from uptimely.spec.validation import errors

logger = logging.getLogger(__name__)


def validate_function_contracts(spec: spec_model.Spec) -> None:
    """Validate function-owned contracts and report spec paths."""
    logger.debug("Check function contracts")
    for function_id, function in spec.functions.root.items():
        checks = (
            (function.check_return_contract, "invalid_function_return_contract", "returns"),
            (function.check_dataframe_input_contract, "invalid_function_input_contract", "args"),
            (function.check_argument_contracts, "invalid_function_input_contract", "args"),
        )
        for check, code, field in checks:
            try:
                check()
            except ValueError as error:
                raise errors.SpecError(
                    str(error),
                    code=code,
                    path=("functions", function_id, field),
                ) from error
