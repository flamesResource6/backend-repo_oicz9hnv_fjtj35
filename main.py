import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Literal
from database import create_document, get_documents
from schemas import Subscription

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ----- Pricing plans (static catalog exposed by backend) -----
class Plan(BaseModel):
    id: str
    name: str
    price: float
    interval: Literal["month", "year"] = "month"
    features: List[str]
    most_popular: bool = False

PRICING_PLANS: List[Plan] = [
    Plan(
        id="starter",
        name="Starter",
        price=9,
        interval="month",
        features=[
            "Unlimited projects",
            "Community support",
            "Basic analytics",
        ],
        most_popular=False,
    ),
    Plan(
        id="pro",
        name="Pro",
        price=29,
        interval="month",
        features=[
            "Everything in Starter",
            "Advanced analytics",
            "Priority support",
            "Team collaboration",
        ],
        most_popular=True,
    ),
    Plan(
        id="business",
        name="Business",
        price=79,
        interval="month",
        features=[
            "Everything in Pro",
            "SLA & SSO",
            "Audit logs",
            "Dedicated success manager",
        ],
        most_popular=False,
    ),
]


@app.get("/")
def read_root():
    return {"message": "Hello from FastAPI Backend!"}


@app.get("/api/plans", response_model=List[Plan])
def list_plans():
    return PRICING_PLANS


class CheckoutRequest(BaseModel):
    plan_id: str = Field(..., description="The plan id selected by the user")
    email: str = Field(..., description="User email (from Clerk or input)")
    user_id: Optional[str] = Field(None, description="Clerk user ID if available")


class CheckoutResponse(BaseModel):
    subscription_id: str
    status: Literal["pending", "active"]
    message: str


@app.post("/api/checkout", response_model=CheckoutResponse)
def checkout(req: CheckoutRequest):
    plan = next((p for p in PRICING_PLANS if p.id == req.plan_id), None)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    # In a real integration, you'd create a payment session (Stripe, etc.) here.
    # For now, we create a subscription record with status 'active' to simulate success.
    sub = Subscription(
        plan_id=plan.id,
        plan_name=plan.name,
        price=plan.price,
        interval=plan.interval,
        email=req.email,
        user_id=req.user_id,
        status="active",
    )

    inserted_id = create_document("subscription", sub)

    return CheckoutResponse(
        subscription_id=inserted_id,
        status=sub.status,
        message=f"Subscription for {plan.name} activated",
    )


@app.get("/api/subscriptions")
def get_user_subscriptions(email: Optional[str] = None, user_id: Optional[str] = None):
    """Fetch subscriptions filtered by email or user_id."""
    filter_dict = {}
    if user_id:
        filter_dict["user_id"] = user_id
    if email:
        filter_dict["email"] = email

    docs = get_documents("subscription", filter_dict or {}, limit=50)
    # Convert ObjectId to string for JSON serialization
    for d in docs:
        if "_id" in d:
            d["_id"] = str(d["_id"]) 
    return {"items": docs}


@app.get("/test")
def test_database():
    """Test endpoint to check if database is available and accessible"""
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    
    try:
        # Try to import database module
        from database import db
        
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            
            # Try to list collections to verify connectivity
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]  # Show first 10 collections
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
            
    except ImportError:
        response["database"] = "❌ Database module not found (run enable-database first)"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"
    
    # Check environment variables
    import os
    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
    
    return response


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
