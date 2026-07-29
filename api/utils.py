from fastapi.responses import JSONResponse


def error_response(code: str, message: str, status_code: int) -> JSONResponse:
    return JSONResponse(
        {
            'status': 'error',
            'code': code,
            'message': message
        },
        status_code=status_code
    )
