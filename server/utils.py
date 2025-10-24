from fastapi.responses import JSONResponse
from fastapi import Request
from motor.motor_asyncio import AsyncIOMotorCollection

def success_response(data: dict, status_code: int = 200):
    return JSONResponse(status_code=status_code, content={"success": True, "data": data})

def error_response(message: str, status_code: int = 400):
    return JSONResponse(
        status_code=status_code,
        content={"success": False, "error": {"code": status_code, "message": message}},
    )

def col_messages(req: Request) -> AsyncIOMotorCollection:
    """Returns the MongoDB 'messages' collection."""
    # This is the original logic moved here
    return req.app.state.db["messages"]