from pydantic.errors import PydanticErrorMixin


class _BaseAppError(PydanticErrorMixin, ValueError):
    @classmethod
    def get_full_class_name(cls) -> str:
        # Can be used as unique code identifier
        return f"{cls.__module__}.{cls.__name__}"


#
# gateway  errors
#


class BasePaymentsGatewayError(_BaseAppError):
    ...


class PaymentsGatewayNotReadyError(BasePaymentsGatewayError):
    msg_template = "Payments-Gateway is unresponsive: {checks}"
