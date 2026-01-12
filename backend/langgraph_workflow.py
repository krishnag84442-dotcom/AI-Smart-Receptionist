from typing import TypedDict, List
import google.generativeai as genai
import os
from dotenv import load_dotenv
from supabase_client import save_patient_data, trigger_webhook
import re

# Load environment variables
load_dotenv()

class ConversationState(TypedDict):
    messages: List[dict]
    patient_name: str
    patient_age: int
    patient_query: str
    ward: str
    current_node: str

# Initialize Google Gemini (optional - not used in current workflow)
google_api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
if google_api_key:
    genai.configure(api_key=google_api_key)
    print("Google Gemini configured successfully")
else:
    print("Warning: GOOGLE_API_KEY or GEMINI_API_KEY not found in environment variables.")
    print("LLM features will not be available.")

def classify_message(message: str) -> str:
    """Classify message into one of three wards based on keywords"""
    message_lower = message.lower()

    # Emergency keywords
    emergency_keywords = ["emergency", "urgent", "accident", "injured", "bleeding", "chest pain", "heart attack", "stroke", "unconscious", "severe pain", "trauma"]
    # Mental health keywords
    mental_health_keywords = ["mental", "depression", "anxiety", "suicidal", "therapy", "psychiatrist", "psychologist", "counseling", "panic", "stress", "emotional", "psychiatric"]

    if any(keyword in message_lower for keyword in emergency_keywords):
        return "emergency_ward"
    elif any(keyword in message_lower for keyword in mental_health_keywords):
        return "mental_health_ward"
    else:
        return "general_ward"

def process_patient_info(messages: List[dict], ward: str) -> dict:
    """Process patient information collection based on conversation history"""
    # Extract information from messages
    patient_data = {
        "name": None,
        "age": None,
        "query": None
    }

    # Get all user messages
    user_messages = [msg.get("content", "") for msg in messages if msg.get("role") == "user"]
    all_user_text = " ".join(user_messages)

    # Extract name from all user messages
    patient_data["name"] = extract_name(all_user_text)

    # Extract age from all user messages
    patient_data["age"] = extract_age(all_user_text)

    # Extract query (use the first substantial user message as the query)
    if user_messages:
        # Use the first user message if it's substantial, otherwise the last one
        first_msg = user_messages[0]
        if len(first_msg) > 10:
            patient_data["query"] = first_msg
        else:
            patient_data["query"] = user_messages[-1]  # Last message

    return patient_data

def handle_conversation(messages: List[dict], ward: str) -> dict:
    """Handle the conversation flow and return response"""
    patient_data = process_patient_info(messages, ward)

    # Check what information we have
    if not patient_data["name"]:
        if ward == "emergency_ward":
            response = "This is the Emergency Ward. I need to collect some information quickly. What is the patient's name?"
        elif ward == "mental_health_ward":
            response = "Thank you for reaching out to the Mental Health Ward. To assist you better, could you please provide your name?"
        else:
            response = "Thank you for contacting the General Ward. May I please have your name?"
    elif not patient_data["age"]:
        response = f"Thank you, {patient_data['name']}. Could you please provide your age?"
        if ward == "emergency_ward":
            response = f"Thank you. What is {patient_data['name']}'s age?"
    elif not patient_data["query"] or len(str(patient_data["query"])) < 10:
        if ward == "emergency_ward":
            response = "Please describe the emergency situation or symptoms."
        elif ward == "mental_health_ward":
            response = "Could you please share what brings you to the Mental Health Ward today?"
        else:
            response = "Could you please describe your concern or the reason for your visit?"
    else:
        # All information collected - save to database and trigger webhook
        print(f"Saving patient data to Supabase: Name={patient_data['name']}, Age={patient_data['age']}, Ward={ward}")

        patient_id = save_patient_data(
            name=patient_data["name"],
            age=patient_data["age"],
            query=patient_data["query"],
            ward=ward
        )

        if patient_id:
            print(f"✓ Patient data successfully saved to Supabase with ID: {patient_id}")
        else:
            print("⚠ Warning: Patient data may not have been saved to Supabase. Please check configuration.")

        # Trigger webhook
        webhook_success = trigger_webhook(
            patient_name=patient_data["name"],
            patient_age=patient_data["age"],
            patient_query=patient_data["query"],
            ward=ward
        )

        ward_display = ward.replace("_", " ").title()
        if patient_id:
            response = f"Thank you, {patient_data['name']}. Your information has been successfully recorded and saved. You've been routed to the {ward_display}. A staff member will be with you shortly."
        else:
            response = f"Thank you, {patient_data['name']}. Your information has been recorded and you've been routed to the {ward_display}. A staff member will be with you shortly."

        if ward == "emergency_ward":
            if patient_id:
                response = f"Emergency information recorded and saved for {patient_data['name']}. Medical staff are being notified immediately."
            else:
                response = f"Emergency information recorded for {patient_data['name']}. Medical staff are being notified immediately."
        elif ward == "mental_health_ward":
            if patient_id:
                response = f"Thank you, {patient_data['name']}. Your information has been saved and sent to the Mental Health Ward. A mental health professional will contact you soon."
            else:
                response = f"Thank you, {patient_data['name']}. Your information has been sent to the Mental Health Ward. A mental health professional will contact you soon."

    return {"response": response, "completed": bool(patient_data["name"] and patient_data["age"] and patient_data["query"])}

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

def process_chat_message(messages: List[dict]) -> str:
    """Process a chat message and return the AI response"""
    # Get the latest user message
    latest_message = ""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            latest_message = msg.get("content", "")
            break

    # Classify the message
    ward = classify_message(latest_message)

    # Handle the conversation
    result = handle_conversation(messages, ward)

    return result["response"]

