from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, List
import os
from dotenv import load_dotenv
from langgraph_workflow import process_chat_message

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Local development
        "https://ai-smartrreceptionist.vercel.app",  # Production frontend
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Store conversation messages per session
conversation_states: Dict[str, List[dict]] = {}

class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"

class ChatResponse(BaseModel):
    response: str

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    try:
        # Get or create conversation messages for this session
        if request.session_id not in conversation_states:
            conversation_states[request.session_id] = []

        messages = conversation_states[request.session_id]

        # Add user message
        messages.append({"role": "user", "content": request.message})

        # Process the message and get response
        response_text = process_chat_message(messages)

        # Add assistant response to conversation
        messages.append({"role": "assistant", "content": response_text})

        # Update conversation state
        conversation_states[request.session_id] = messages

        return ChatResponse(response=response_text)

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health():
    return {"status": "ok"}

# For production deployment (Render, etc.)
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "0.0.0.0")
    print(f"Starting FastAPI server on {host}:{port}")
    uvicorn.run(app, host=host, port=port)

# Export app for uvicorn/gunicorn
__all__ = ["app"]

