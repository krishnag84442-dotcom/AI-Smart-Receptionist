# AI-Powered Hospital Receptionist

A minimal AI-powered hospital receptionist system that understands patient queries, routes them to the correct ward, collects required patient details, and sends data via webhook.

## Features

- Natural language patient query processing
- Automatic ward classification (General, Emergency, Mental Health)
- Patient information collection (Name, Age, Query)
- One-question-at-a-time clarification flow
- Supabase database integration
- Webhook notifications when data collection is complete

## Tech Stack

- **Frontend**: React + Vite
- **Backend**: Python + FastAPI
- **AI/Workflow**: LangGraph
- **Database**: Supabase (PostgreSQL)

## Setup

### Prerequisites

- Node.js 18+ and npm
- Python 3.9+
- Supabase account
- Google Gemini API key

### Backend Setup

1. Navigate to the backend directory:
```bash
cd backend
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up environment variables:
```bash
cp .env.example .env
```

Edit `.env` and add your credentials:
- `GOOGLE_API_KEY`: Your Google Gemini API key
- `SUPABASE_URL`: Your Supabase project URL
- `SUPABASE_KEY`: Your Supabase anon/service key
- `WEBHOOK_URL`: (Optional) Your webhook endpoint URL

5. Set up Supabase database:

Run the SQL from `backend/supabase_setup.sql` in your Supabase SQL editor, or copy and paste the contents:

```bash
# The SQL file is located at backend/supabase_setup.sql
```

This will create the `patients` table with proper indexes.

6. Start the backend server:
```bash
python main.py
```

The backend will run on `http://localhost:8000`

### Frontend Setup

1. Navigate to the frontend directory:
```bash
cd frontend
```

2. Install dependencies:
```bash
npm install
```

3. Start the development server:
```bash
npm run dev
```

The frontend will run on `http://localhost:3000`

## API Endpoints

### POST /chat

Send a patient message and receive an AI response.

**Request:**
```json
{
  "message": "I need emergency help",
  "session_id": "default"
}
```

**Response:**
```json
{
  "response": "This is the Emergency Ward. I need to collect some information quickly. What is the patient's name?"
}
```

### GET /health

Health check endpoint.

## Ward Classification Rules

- **Emergency Ward**: Keywords like "emergency", "urgent", "accident", "injured", "bleeding", "chest pain", etc.
- **Mental Health Ward**: Keywords like "mental", "depression", "anxiety", "therapy", "psychiatrist", etc.
- **General Ward**: All other queries

## Webhook Payload

When all patient information is collected, a webhook is triggered with:

```json
{
  "patient_name": "John Doe",
  "patient_age": 35,
  "patient_query": "I have a fever and cough",
  "ward": "general_ward"
}
```

## Project Structure

```
.
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── App.css
│   │   ├── main.jsx
│   │   └── index.css
│   ├── package.json
│   └── vite.config.js
├── backend/
│   ├── main.py
│   ├── langgraph_workflow.py
│   ├── supabase_client.py
│   ├── requirements.txt
│   └── .env.example
└── README.md
```

## Notes

- The system maintains conversation state per session ID
- Patient information is collected one field at a time
- Webhook is only triggered when all required fields (name, age, query) are present
- Database save failures are logged but don't block the conversation flow

