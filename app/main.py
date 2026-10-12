# from typing import Dict
# from app.auth import router as auth_router
# from fastapi import FastAPI, HTTPException, Depends
# from fastapi.security import HTTPBasic, HTTPBasicCredentials
#
#
# app = FastAPI()
# app.include_router(auth_router)
# security = HTTPBasic()
#
# # Dummy user database
# users_db: Dict[str, Dict[str, str]] = {
#     "Tony": {"password": "password123", "role": "engineering"},
#     "Peter": {"password": "pete123", "role": "engineering"},
#
#     "Sam": {"password": "financepass", "role": "finance"},
#
#     "Bruce": {"password": "securepass", "role": "marketing"},
#     "Sid": {"password": "sidpass123", "role": "marketing"},
#
#     "Natasha": {"password": "hrpass123", "role": "hr"},
#
#     "Employeedemo1": {"password": "employee_demo_123","role": "employee"},
#
#     "ExecutiveDemo1": {"password": "executive_demo_123","role": "c_level"}
# }
#
#
# # Authentication dependency
# def authenticate(credentials: HTTPBasicCredentials = Depends(security)):
#     username = credentials.username
#     password = credentials.password
#     user = users_db.get(username)
#     if not user or user["password"] != password:
#         raise HTTPException(status_code=401, detail="Invalid credentials")
#     return {"username": username, "role": user["role"]}
#
#
# # Login endpoint
# @app.get("/login")
# def login(user=Depends(authenticate)):
#     return {"message": f"Welcome {user['username']}!you are now log in", "role": user["role"]}
#
#
# # Protected test endpoint
# @app.get("/test")
# def test(user=Depends(authenticate)):
#     return {"message": f"Hello {user['username']}! You can now chat.this it a test", "role": user["role"]}
#
#
# # Protected chat endpoint
# @app.post("/chat")
# def query(user=Depends(authenticate), message: str = "Hello"):
#     return "Implement this endpoint."









#在main.py中，我们建立起了python并跑起了starter——这是由fastAPI实现 的
#此外，在main.py中，我们还实现了登录以及角色分配

from fastapi import Depends, FastAPI, HTTPException, Query
from app.chunking import chunk_documents
from app.loaders import list_authorized_files, load_authorized_documents
from app.auth import get_current_user, router as auth_router
from pydantic import BaseModel, ConfigDict, Field

from app.retrieval import retrieve
from app.hr_queries import (get_employee,count_records,average_salary,)
from app.rag import generate_rag_answer

app = FastAPI()
app.include_router(auth_router)


@app.get("/me")
def me(user: dict = Depends(get_current_user)):
    return user


@app.get("/test")
def test(user: dict = Depends(get_current_user)):
    return {
        "message": f"Hello {user['username']}! JWT 验证成功。",
        "role": user["app_role"],
    }


# @app.post("/chat")
# def query(
#     message: str = "Hello",
#     user: dict = Depends(get_current_user),
# ):
#     return {
#         "message": "身份验证已通过，聊天功能尚未实现。",
#         "username": user["username"],
#     }

@app.get("/files")
def files(user: dict = Depends(get_current_user)):
    # 使用数据库中的真实角色，不由用户自行填写角色
    visible_files = list_authorized_files(user["app_role"])

    return {
        "username": user["username"],
        "app_role": user["app_role"],
        "file_count": len(visible_files),
        "files": visible_files,
    }

@app.get("/documents/preview")
def preview_documents(user: dict = Depends(get_current_user)):
    documents = load_authorized_documents(user["app_role"])

    # 预览只返回前三条的部分正文，避免页面被大量文本占满
    samples = [
        {
            "document_id": doc["document_id"],
            "title": doc["title"],
            "headings": doc["headings"][:5],
            "content_preview": doc["content"][:500],
            "metadata": doc["metadata"],
        }
        for doc in documents[:3]
    ]

    return {
        "username": user["username"],
        "app_role": user["app_role"],
        "document_count": len(documents),
        "samples": samples,
    }


@app.get("/chunks/preview")
def preview_chunks(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=3, ge=1, le=10),
    user: dict = Depends(get_current_user),
):
    documents = load_authorized_documents(user["app_role"])
    try:
        chunks = chunk_documents(documents)
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error

    return {
        "username": user["username"],
        "app_role": user["app_role"],
        "document_count": len(documents),
        "chunk_count": len(chunks),
        "offset": offset,
        "samples": chunks[offset:offset + limit],
    }

class SearchRequest(BaseModel):
    # 请求只能包含下面定义的字段。
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1, max_length=1000)
    top_k: int = Field(default=5, ge=1, le=10)

    source_file: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
    )


@app.post("/search")
def search(
    request: SearchRequest,
    user: dict = Depends(get_current_user),
):
    try:
        matches = retrieve(
            question=request.question,
            user=user,
            top_k=request.top_k,
            source_file=request.source_file,
        )

    except ValueError as error:
        raise HTTPException(
            status_code=422,
            detail=str(error),
        ) from error

    except PermissionError as error:
        raise HTTPException(
            status_code=403,
            detail=str(error),
        ) from error

    except RuntimeError as error:
        raise HTTPException(
            status_code=503,
            detail=str(error),
        ) from error

    response = {
        "username": user["username"],
        "app_role": user["app_role"],
        "question": request.question.strip(),
        "result_count": len(matches),
        "results": matches,
    }

    return response





@app.get("/hr/employees/{employee_id}")
def get_employee_record(
    employee_id: str,
    user: dict = Depends(get_current_user),
):
    try:
        result = get_employee(
            employee_id=employee_id,
            user=user,
        )
    except PermissionError as error:
        raise HTTPException(
            status_code=403,
            detail=str(error),
        ) from error
    except ValueError as error:
        raise HTTPException(
            status_code=422,
            detail=str(error),
        ) from error
    except (OSError, RuntimeError) as error:
        raise HTTPException(
            status_code=503,
            detail="HR 数据暂时不可用",
        ) from error

    return result




@app.get("/hr/statistics/count")
def get_hr_record_count(
    employee_department: str | None = None,
    user: dict = Depends(get_current_user),
):
    try:
        result = count_records(
            user=user,
            employee_department=employee_department,
        )
    except PermissionError as error:
        raise HTTPException(
            status_code=403,
            detail=str(error),
        ) from error
    except ValueError as error:
        raise HTTPException(
            status_code=422,
            detail=str(error),
        ) from error
    except (OSError, RuntimeError) as error:
        raise HTTPException(
            status_code=503,
            detail="HR 数据暂时不可用",
        ) from error

    return result


@app.get("/hr/statistics/average-salary")
def get_hr_average_salary(
    employee_department: str | None = None,
    user: dict = Depends(get_current_user),
):
    try:
        result = average_salary(
            user=user,
            employee_department=employee_department,
        )
    except PermissionError as error:
        raise HTTPException(
            status_code=403,
            detail=str(error),
        ) from error
    except ValueError as error:
        raise HTTPException(
            status_code=422,
            detail=str(error),
        ) from error
    except (OSError, RuntimeError) as error:
        raise HTTPException(
            status_code=503,
            detail="HR 数据暂时不可用",
        ) from error

    return result



#检索资料、调用大模型和返回回答，由后面的函数体完成
@app.post("/chat")
def chat(
    request: SearchRequest,
    user: dict = Depends(get_current_user),
):
    try:
        result = generate_rag_answer(#request 包含问题、检索数量，以及可选的文件路径。
            question=request.question,
            user=user,
            top_k=request.top_k,
            source_file=request.source_file,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=422,
            detail=str(error),
        ) from error
    except PermissionError as error:
        raise HTTPException(
            status_code=403,
            detail=str(error),
        ) from error
    except RuntimeError as error:
        raise HTTPException(
            status_code=503,
            detail=str(error),
        ) from error

    return {
        "username": user["username"],
        "app_role": user["app_role"],
        "question": request.question.strip(),
        "result": result,
    }

















































