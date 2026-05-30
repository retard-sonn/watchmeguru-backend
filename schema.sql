-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- ═══════════════════════════════════════════════════
-- Clerk-synced users table
-- Auto-populated by the FastAPI ClerkAuthMiddleware
-- on every authenticated API request.
-- ═══════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    clerk_user_id TEXT UNIQUE NOT NULL,
    email TEXT,
    first_name TEXT,
    last_name TEXT,
    profile_image_url TEXT,
    last_synced_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Table for students
CREATE TABLE IF NOT EXISTS students (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    clerk_user_id TEXT REFERENCES users(clerk_user_id),
    name TEXT NOT NULL,
    whatsapp_number TEXT UNIQUE NOT NULL,
    exam_type TEXT,
    exam_date DATE,
    weak_subjects TEXT[],
    daily_schedule JSONB,
    guardian_contact TEXT,
    preferred_platforms TEXT[] DEFAULT '{"whatsapp"}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Table for daily micro-tasks
CREATE TABLE IF NOT EXISTS tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id UUID REFERENCES students(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    description TEXT,
    status TEXT DEFAULT 'pending', -- pending, completed, missed
    due_date TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Table for tracking interactions
CREATE TABLE IF NOT EXISTS interactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id UUID REFERENCES students(id) ON DELETE CASCADE,
    direction TEXT NOT NULL, -- inbound, outbound
    message_type TEXT, -- text, voice
    platform TEXT DEFAULT 'whatsapp', -- whatsapp, instagram, telegram, discord
    content TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Table for vector chat memory
CREATE TABLE IF NOT EXISTS chat_memory (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id UUID REFERENCES students(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    embedding vector(768), -- assuming Gemini text-embedding-004 which has 768 dims
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Table for surprise quizzes
CREATE TABLE IF NOT EXISTS quizzes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id UUID REFERENCES students(id) ON DELETE CASCADE,
    question TEXT NOT NULL,
    expected_answer TEXT,
    student_answer TEXT,
    score TEXT, -- Correct, Partial, Incorrect
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    answered_at TIMESTAMP WITH TIME ZONE
);
