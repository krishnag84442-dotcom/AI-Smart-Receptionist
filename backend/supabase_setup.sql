-- Create patients table for storing patient information
CREATE TABLE IF NOT EXISTS patients (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  patient_name TEXT NOT NULL,
  patient_age INTEGER NOT NULL,
  patient_query TEXT NOT NULL,
  ward TEXT NOT NULL CHECK (ward IN ('general_ward', 'emergency_ward', 'mental_health_ward')),
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create an index on created_at for faster queries
CREATE INDEX IF NOT EXISTS idx_patients_created_at ON patients(created_at);

-- Create an index on ward for filtering
CREATE INDEX IF NOT EXISTS idx_patients_ward ON patients(ward);

