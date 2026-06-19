from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware

from mangum import Mangum
from auth import get_current_user
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://clauseiq.com", "http://localhost:5173"],
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/me")
def me(user=Depends(get_current_user)):
    return {"userId": user["userId"]}

from routers import agreements, chat

app.include_router(agreements.router)
app.include_router(chat.router)

handler = Mangum(app)


