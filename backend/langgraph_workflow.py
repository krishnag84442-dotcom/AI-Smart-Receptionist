from typing import TypedDict, Annotated, Literal
from langgraph.graph import StateGraph, END
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, AIMessage
import os
from dotenv import load_dotenv
from supabase_client import save_patient_data, trigger_webhook
import re

# Load environment variables before initializing LLM
load_dotenv()

class ConversationState(TypedDict):
    messages: Annotated[list, lambda x, y: x + y]
    patient_name: str | None
    patient_age: int | None
    patient_query: str | None
    ward: Literal["general_ward", "emergency_ward", "mental_health_ward"] | None
    current_node: str

# Initialize LLM - Google Gemini
# API key is read from GOOGLE_API_KEY or GEMINI_API_KEY environment variable
# Note: LLM is initialized but currently not used in the workflow (keyword matching is used instead)
# This can be used for future enhancements like LLM-based classification
llm = None
google_api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
if google_api_key:
    # Ensure the key is set in environment for ChatGoogleGenerativeAI
    os.environ["GOOGLE_API_KEY"] = google_api_key
    try:
        llm = ChatGoogleGenerativeAI(
            model="models/gemini-1.5-flash",
            temperature=0.2
        )
    except Exception as e:
        print(f"Warning: Could not initialize Gemini LLM: {e}")
        llm = None
else:
    print("Warning: GOOGLE_API_KEY or GEMINI_API_KEY not found in environment variables.")
    print("The server will start but LLM features will not be available.")

def start_node(state: ConversationState) -> ConversationState:
    """Receive user input and forward to router or continue in current ward"""
    # If we already have a ward assigned, continue in that ward
    if state.get("ward") and state.get("current_node") != "start":
        return {
            "current_node": state.get("ward", "router")
        }
    return {
        "current_node": "router"
    }

def router_node(state: ConversationState) -> ConversationState:
    """Classify intent into one of three wards"""
    last_message = ""
    if state["messages"]:
        last_msg = state["messages"][-1]
        if isinstance(last_msg, HumanMessage):
            last_message = last_msg.content.lower()
        elif hasattr(last_msg, "get"):
            last_message = last_msg.get("content", "").lower()
        else:
            last_message = str(last_msg).lower()
    
    # Emergency keywords
    emergency_keywords = ["emergency", "urgent", "accident", "injured", "bleeding", "chest pain", "heart attack", "stroke", "unconscious", "severe pain", "trauma"]
    # Mental health keywords
    mental_health_keywords = ["mental", "depression", "anxiety", "suicidal", "therapy", "psychiatrist", "psychologist", "counseling", "panic", "stress", "emotional", "psychiatric"]
    
    ward = "general_ward"
    
    if any(keyword in last_message for keyword in emergency_keywords):
        ward = "emergency_ward"
    elif any(keyword in last_message for keyword in mental_health_keywords):
        ward = "mental_health_ward"
    
    return {
        "ward": ward,
        "current_node": ward
    }

def general_ward_node(state: ConversationState) -> ConversationState:
    """Collect patient information for general ward"""
    return collect_patient_info(state, "general_ward")

def emergency_ward_node(state: ConversationState) -> ConversationState:
    """Collect patient information for emergency ward"""
    return collect_patient_info(state, "emergency_ward")

def mental_health_ward_node(state: ConversationState) -> ConversationState:
    """Collect patient information for mental health ward"""
    return collect_patient_info(state, "mental_health_ward")

def collect_patient_info(state: ConversationState, ward: str) -> ConversationState:
    """Collect patient information and ask clarification questions"""
    last_user_message = ""
    for msg in reversed(state["messages"]):
        if isinstance(msg, HumanMessage) or (hasattr(msg, "get") and msg.get("role") == "user"):
            if isinstance(msg, HumanMessage):
                last_user_message = msg.content
            else:
                last_user_message = msg.get("content", "")
            break
    
    # Extract patient name if not set
    if not state.get("patient_name"):
        name = extract_name(last_user_message)
        if name:
            new_state = dict(state)
            new_state["patient_name"] = name
            # Continue to check other fields
            return collect_patient_info(new_state, ward)
        else:
            response = "Thank you for contacting the General Ward. May I please have your name?"
            if ward == "emergency_ward":
                response = "This is the Emergency Ward. I need to collect some information quickly. What is the patient's name?"
            elif ward == "mental_health_ward":
                response = "Thank you for reaching out to the Mental Health Ward. To assist you better, could you please provide your name?"
            
            new_state = dict(state)
            new_state["messages"] = state["messages"] + [AIMessage(content=response)]
            return new_state
    
    # Extract patient age if not set
    if not state.get("patient_age"):
        age = extract_age(last_user_message)
        if age:
            new_state = dict(state)
            new_state["patient_age"] = age
            # Continue to check query
            return collect_patient_info(new_state, ward)
        else:
            response = f"Thank you, {state['patient_name']}. Could you please provide your age?"
            if ward == "emergency_ward":
                response = f"Thank you. What is {state['patient_name']}'s age?"
            new_state = dict(state)
            new_state["messages"] = state["messages"] + [AIMessage(content=response)]
            return new_state
    
    # Extract patient query if not set
    if not state.get("patient_query"):
        # Check if last message contains substantial query info
        # Get the first user message that might contain the query
        first_user_msg = ""
        for msg in state["messages"]:
            if isinstance(msg, HumanMessage) or (hasattr(msg, "get") and msg.get("role") == "user"):
                if isinstance(msg, HumanMessage):
                    first_user_msg = msg.content
                else:
                    first_user_msg = msg.get("content", "")
                if len(first_user_msg) > 10:
                    break
        
        query = first_user_msg if len(first_user_msg) > 10 else last_user_message
        
        if not query or len(query) < 10:
            response = f"Thank you. Could you please describe your concern or the reason for your visit?"
            if ward == "emergency_ward":
                response = f"Please describe the emergency situation or symptoms."
            elif ward == "mental_health_ward":
                response = f"Could you please share what brings you to the Mental Health Ward today?"
            new_state = dict(state)
            new_state["messages"] = state["messages"] + [AIMessage(content=response)]
            return new_state
        else:
            new_state = dict(state)
            new_state["patient_query"] = query
            # Continue to save and webhook
            return collect_patient_info(new_state, ward)
    
    # All information collected - save to database and trigger webhook
    # Only do this once (check if we already sent the completion message)
    last_assistant_msg = ""
    for msg in reversed(state["messages"]):
        if isinstance(msg, AIMessage) or (hasattr(msg, "get") and msg.get("role") == "assistant"):
            if isinstance(msg, AIMessage):
                last_assistant_msg = msg.content
            else:
                last_assistant_msg = msg.get("content", "")
            break
    
    if "recorded" not in last_assistant_msg.lower() and "notified" not in last_assistant_msg.lower():
        # Save to Supabase - this is the critical step
        print(f"Saving patient data to Supabase: Name={state['patient_name']}, Age={state['patient_age']}, Ward={ward}")
        patient_id = save_patient_data(
            name=state["patient_name"],
            age=state["patient_age"],
            query=state["patient_query"],
            ward=ward
        )
        
        if patient_id:
            print(f"✓ Patient data successfully saved to Supabase with ID: {patient_id}")
        else:
            print("⚠ Warning: Patient data may not have been saved to Supabase. Please check configuration.")
        
        # Trigger webhook
        webhook_success = trigger_webhook(
            patient_name=state["patient_name"],
            patient_age=state["patient_age"],
            patient_query=state["patient_query"],
            ward=ward
        )
        
        ward_display = ward.replace("_", " ").title()
        if patient_id:
            response = f"Thank you, {state['patient_name']}. Your information has been successfully recorded and saved. You've been routed to the {ward_display}. A staff member will be with you shortly."
        else:
            response = f"Thank you, {state['patient_name']}. Your information has been recorded and you've been routed to the {ward_display}. A staff member will be with you shortly."
        
        if ward == "emergency_ward":
            if patient_id:
                response = f"Emergency information recorded and saved for {state['patient_name']}. Medical staff are being notified immediately."
            else:
                response = f"Emergency information recorded for {state['patient_name']}. Medical staff are being notified immediately."
        elif ward == "mental_health_ward":
            if patient_id:
                response = f"Thank you, {state['patient_name']}. Your information has been saved and sent to the Mental Health Ward. A mental health professional will contact you soon."
            else:
                response = f"Thank you, {state['patient_name']}. Your information has been sent to the Mental Health Ward. A mental health professional will contact you soon."
        
        new_state = dict(state)
        new_state["messages"] = state["messages"] + [AIMessage(content=response)]
        new_state["current_node"] = "end"
        return new_state
    
    return state

def extract_name(text: str) -> str | None:
    """Extract name from text using simple patterns"""
    # Look for patterns like "I'm John", "My name is John", "This is John"
    patterns = [
        r"(?:i'?m|i am|my name is|this is|name is)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
        r"^([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)(?:\s|$)",
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    
    # If text is short and looks like a name
    words = text.strip().split()
    if len(words) <= 3 and all(word[0].isupper() for word in words if word):
        return text.strip()
    
    return None

def extract_age(text: str) -> int | None:
    """Extract age from text"""
    # Look for age patterns
    patterns = [
        r"(?:i'?m|i am|age is|aged)\s+(\d+)",
        r"(\d+)\s*(?:years? old|yrs? old|years? of age)",
        r"^(\d+)$",
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                age = int(match.group(1))
                if 0 < age < 150:  # Reasonable age range
                    return age
            except ValueError:
                pass
    
    return None

def create_workflow():
    """Create and return the LangGraph workflow"""
    workflow = StateGraph(ConversationState)
    
    # Add nodes
    workflow.add_node("start", start_node)
    workflow.add_node("router", router_node)
    workflow.add_node("general_ward", general_ward_node)
    workflow.add_node("emergency_ward", emergency_ward_node)
    workflow.add_node("mental_health_ward", mental_health_ward_node)
    
    # Set entry point
    workflow.set_entry_point("start")
    
    # Add edges
    workflow.add_conditional_edges(
        "start",
        lambda state: state.get("current_node", "router"),
        {
            "router": "router",
            "general_ward": "general_ward",
            "emergency_ward": "emergency_ward",
            "mental_health_ward": "mental_health_ward"
        }
    )
    
    workflow.add_conditional_edges(
        "router",
        lambda state: state.get("ward", "general_ward"),
        {
            "general_ward": "general_ward",
            "emergency_ward": "emergency_ward",
            "mental_health_ward": "mental_health_ward"
        }
    )
    
    # All ward nodes end after processing
    workflow.add_edge("general_ward", END)
    workflow.add_edge("emergency_ward", END)
    workflow.add_edge("mental_health_ward", END)
    
    return workflow.compile()

