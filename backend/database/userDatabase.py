from fastapi import HTTPException, APIRouter, status
from pydantic import BaseModel, Field
from motor.motor_asyncio import AsyncIOMotorClient
from passlib.hash import bcrypt
import os

# --- MongoDB Setup ---
MONGO_URI = os.getenv("MONGO_URI")
mongo_client = AsyncIOMotorClient(MONGO_URI)
db = mongo_client["USERS"]  # Your DB name


# --- Pydantic Schemas ---
class UserCreate(BaseModel):
    username: str
    password: str = Field(min_length=6)
    role: str

class UserOut(BaseModel):
    username: str
    role: str

router = APIRouter()


# --- User Functions ---
@router.post("/users")
async def create_user(user_data: UserCreate) -> UserOut:
    try:
        if not user_data.username or not user_data.password or not user_data.role:
            raise HTTPException(status_code=400, detail="All fields are required")
        existing = await db.users.find_one({"username": user_data.username})
        if existing:
            raise HTTPException(status_code=400, detail="User already exists")
        hashed_pw = bcrypt.hash(user_data.password)
        user_doc = {
            "username": user_data.username,
            "password": hashed_pw,
            "role": user_data.role,
        }
        await db.users.insert_one(user_doc)
        return UserOut(username=user_data.username, role=user_data.role)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/users/{username}")
async def validate_user(username: str, password: str) -> UserOut:
    try:
        if not username or not password:
            raise HTTPException(status_code=400, detail="Username and password are required")
        user = await db.users.find_one({"username": username})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        if not bcrypt.verify(password, user["password"]):
            raise HTTPException(status_code=401, detail="Invalid password")
        return UserOut(username=user["username"], role=user["role"])
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
