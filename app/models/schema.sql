-- Supabase PostgreSQL Schema for WatchMeGuru Omni-Channel

-- 1. Users / Students
CREATE TABLE IF NOT EXISTS students (
    id UUID PRIMARY KEY, -- Matches Clerk ID or generated UUID
    name TEXT NOT NULL,
    whatsapp_number TEXT,
    telegram_handle TEXT,
    discord_id TEXT,
    preferred_channel TEXT DEFAULT 'dashboard', -- 'dashboard', 'whatsapp', 'discord', 'telegram'
    exam_type TEXT,
    exam_date DATE,
    weak_subjects TEXT[],
    guardian_contact TEXT,
    day_streak INTEGER DEFAULT 0,
    escalation_level INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 2. Schedules (The locked grid)
CREATE TABLE IF NOT EXISTS schedules (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    student_id UUID REFERENCES students(id) ON DELETE CASCADE,
    schedule_json JSONB NOT NULL,
    locked_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 3. Daily Blocks (Tasks derived from Schedule)
CREATE TABLE IF NOT EXISTS study_blocks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    student_id UUID REFERENCES students(id) ON DELETE CASCADE,
    day_of_week TEXT NOT NULL,
    label TEXT NOT NULL,
    hours NUMERIC NOT NULL,
    start_time TEXT NOT NULL,
    status TEXT DEFAULT 'pending', -- 'pending', 'completed', 'missed'
    date DATE DEFAULT CURRENT_DATE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 4. Conversation Memory (LangGraph State persistence)
CREATE TABLE IF NOT EXISTS conversation_memory (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    student_id UUID REFERENCES students(id) ON DELETE CASCADE,
    role TEXT NOT NULL, -- 'user', 'assistant'
    content TEXT NOT NULL,
    platform TEXT NOT NULL, -- 'whatsapp', 'discord'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
