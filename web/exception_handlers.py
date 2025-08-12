from fastapi import status, HTTPException
from fastapi.responses import JSONResponse
from fastapi.requests import Request
from sqlalchemy.exc import IntegrityError
from fastapi.exceptions import RequestValidationError




async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": "Ошибка валидации данных. Проверьте ваш запрос."}
    )

async def integrity_error_handler(request: Request, exc: IntegrityError):
    """Обрабатывает ошибки целостности данных из базы данных."""
    # Пример: обработка ошибки уникальности
    if "UniqueViolationError" in str(exc):
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"detail": "Пользователь с такими данными уже существует."}
        )
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": "Ошибка целостности данных."}
    )

async def http_exception_handler(request: Request, exc: HTTPException):
    """Стандартный обработчик для FastAPI HTTPException."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=exc.headers
    )

async def catch_all_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Произошла непредвиденная ошибка на сервере."}
    )