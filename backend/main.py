from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any
import os
from dotenv import load_dotenv
from langgraph_workflow import create_workflow, ConversationState
from langchain_core.messages import HumanMessage, AIMessage

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

# Initialize workflow
workflow = create_workflow()

# Store conversation states per session
conversation_states: Dict[str, dict] = {}

class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"

class ChatResponse(BaseModel):
    response: str

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    try:
        # Get or create conversation state
        if request.session_id not in conversation_states:
            conversation_states[request.session_id] = {
                "messages": [],
                "patient_name": None,
                "patient_age": None,
                "patient_query": None,
                "ward": None,
                "current_node": "start"
            }
        
        state = conversation_states[request.session_id]
        
        # Add user message as HumanMessage
        state["messages"].append(HumanMessage(content=request.message))
        
        # Run workflow
        result = await workflow.ainvoke({
            "messages": state["messages"],
            "patient_name": state["patient_name"],
            "patient_age": state["patient_age"],
            "patient_query": state["patient_query"],
            "ward": state["ward"],
            "current_node": state["current_node"]
        })
        
        # Update state
        conversation_states[request.session_id] = {
            "messages": result["messages"],
            "patient_name": result.get("patient_name"),
            "patient_age": result.get("patient_age"),
            "patient_query": result.get("patient_query"),
            "ward": result.get("ward"),
            "current_node": result.get("current_node", "start")
        }
        
        # Get last assistant message
        assistant_messages = [
            msg for msg in result["messages"] 
            if isinstance(msg, AIMessage) or (hasattr(msg, "role") and msg.get("role") == "assistant")
        ]
        
        if assistant_messages:
            last_msg = assistant_messages[-1]
            if isinstance(last_msg, AIMessage):
                response_text = last_msg.content
            elif hasattr(last_msg, "get"):
                response_text = last_msg.get("content", "I'm here to help. How can I assist you?")
            else:
                response_text = str(last_msg)
        else:
            response_text = "I'm here to help. How can I assist you?"
        
        return ChatResponse(response=response_text)
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

