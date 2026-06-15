class AppException(Exception):
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class NotFoundError(AppException):
    def __init__(self, resource: str, identifier: str | int):
        super().__init__(f"{resource} '{identifier}' not found", status_code=404)


class BadRequestError(AppException):
    def __init__(self, message: str):
        super().__init__(message, status_code=400)


class UnauthorizedError(AppException):
    def __init__(self, message: str = "Unauthorized"):
        super().__init__(message, status_code=401)


class ForbiddenError(AppException):
    def __init__(self, message: str = "Forbidden"):
        super().__init__(message, status_code=403)


class ConflictError(AppException):
    def __init__(self, message: str):
        super().__init__(message, status_code=409)


class ValidationError(AppException):
    def __init__(self, message: str):
        super().__init__(message, status_code=422)
