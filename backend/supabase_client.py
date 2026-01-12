import os
from supabase import create_client, Client
from typing import Optional
import httpx
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Supabase configuration
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")

supabase: Optional[Client] = None

def get_supabase_client() -> Client:
    """Get or create Supabase client"""
    global supabase
    if supabase is None:
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set in environment variables")
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    return supabase

def save_patient_data(name: str, age: int, query: str, ward: str) -> Optional[str]:
    """Save patient data to Supabase and return patient ID"""
    try:
        # Check if Supabase credentials are configured
        if not SUPABASE_URL or not SUPABASE_KEY:
            print("Warning: SUPABASE_URL or SUPABASE_KEY not configured. Patient data will not be saved.")
            return None
        
        client = get_supabase_client()
        
        # Insert patient data
        print(f"Attempting to save patient data to Supabase: {name}, {age}, {ward}")
        result = client.table("patients").insert({
            "patient_name": name,
            "patient_age": age,
            "patient_query": query,
            "ward": ward
        }).execute()
        
        if result.data and len(result.data) > 0:
            patient_id = result.data[0].get("id")
            print(f"Successfully saved patient data to Supabase. Patient ID: {patient_id}")
            return patient_id
        else:
            print("Warning: Supabase insert returned no data")
            return None
    except ValueError as e:
        print(f"Configuration error: {e}")
        return None
    except Exception as e:
        print(f"Error saving to Supabase: {e}")
        import traceback
        traceback.print_exc()
        # Continue even if database save fails
        return None

def trigger_webhook(patient_name: str, patient_age: int, patient_query: str, ward: str) -> bool:
    """Trigger webhook with patient data"""
    if not WEBHOOK_URL:
        print("WEBHOOK_URL not set, skipping webhook")
        return False
    
    try:
        payload = {
            "patient_name": patient_name,
            "patient_age": patient_age,
            "patient_query": patient_query,
            "ward": ward
        }
        
        response = httpx.post(WEBHOOK_URL, json=payload, timeout=10.0)
        response.raise_for_status()
        print(f"Webhook triggered successfully: {response.status_code}")
        return True
    except Exception as e:
        print(f"Error triggering webhook: {e}")
        return False

