# api.py

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict
from .simulator import CustomerSimulator
import uuid

app = FastAPI(
    title="Customer Simulator API",
    description="API to simulate realistic customer conversations",
    version="1.0"
)

# Store active sessions in memory
sessions: Dict[str, CustomerSimulator] = {}


# ---------- Request Models ----------

class StartSessionRequest(BaseModel):
    persona: str = "frustrated"
    scenario: str = "delayed_order"
    initial_emotion: str = "frustrated"
    severity: str = "medium"
    patience: int = 5


class MessageRequest(BaseModel):
    session_id: str
    agent_response: str


# ---------- API Endpoints ----------

@app.get("/")
def home():
    return {
        "message": "Customer Simulator API is running!",
        "docs": "Go to /docs to test the API"
    }


@app.post("/start_session")
def start_session(request: StartSessionRequest):
    """
    Start a new customer simulation session
    """
    try:
        session_id = str(uuid.uuid4())

        simulator = CustomerSimulator(
            persona=request.persona,
            scenario=request.scenario,
            initial_emotion=request.initial_emotion,
            severity=request.severity,
            patience=request.patience
        )

        sessions[session_id] = simulator

        # Generate first customer message
        first_message = simulator.generate_next_message(
            "Hello! Welcome to customer support. How can I help you today?"
        )

        return {
            "session_id": session_id,
            "customer_message": first_message,
            "current_emotion": simulator.emotion_manager.emotion,
            "intensity": simulator.emotion_manager.intensity
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/send_message")
def send_message(request: MessageRequest):
    """
    Send support agent message and get next customer reply
    """
    simulator = sessions.get(request.session_id)

    if not simulator:
        raise HTTPException(status_code=404, detail="Session not found. Please start a new session.")

    try:
        customer_message = simulator.generate_next_message(request.agent_response)

        return {
            "session_id": request.session_id,
            "customer_message": customer_message,
            "current_emotion": simulator.emotion_manager.emotion,
            "intensity": simulator.emotion_manager.intensity
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/session/{session_id}")
def get_session_info(session_id: str):
    """
    Get current session information
    """
    simulator = sessions.get(session_id)

    if not simulator:
        raise HTTPException(status_code=404, detail="Session not found")

    return {
        "session_id": session_id,
        "persona": simulator.persona["name"],
        "scenario": simulator.scenario["name"],
        "current_emotion": simulator.emotion_manager.emotion,
        "intensity": simulator.emotion_manager.intensity,
        "turns": len(simulator.history)
    }


@app.post("/end_session/{session_id}")
def end_session(session_id: str):
    """
    End the session and save the conversation log
    """
    simulator = sessions.get(session_id)

    if not simulator:
        raise HTTPException(status_code=404, detail="Session not found")

    simulator.save_conversation()
    del sessions[session_id]

    return {
        "message": "Session ended and conversation saved successfully",
        "session_id": session_id
    }