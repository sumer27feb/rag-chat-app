from fastapi.responses import JSONResponse

def success_response(data: dict, status_code: int = 200):
    return JSONResponse(status_code=status_code, content={"success": True, "data": data})

def error_response(message: str, status_code: int = 400):
    return JSONResponse(
        status_code=status_code,
        content={"success": False, "error": {"code": status_code, "message": message}},
    )