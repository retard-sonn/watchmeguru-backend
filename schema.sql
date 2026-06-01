-- ═══════════════════════════════════════════════════
-- WatchMeGuru Production Schema
-- ═══════════════════════════════════════════════════

-- Clerk-synced users table
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

-- Students table
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
    guardian_email TEXT,
    student_email TEXT,
    preferred_platforms TEXT[] DEFAULT '{"whatsapp"}',
    mode TEXT DEFAULT 'own_pace',
    day_streak INTEGER DEFAULT 0,
    tasks_completed INTEGER DEFAULT 0,
    study_hours NUMERIC DEFAULT 0,
    quiz_accuracy NUMERIC DEFAULT 0,
    escalation_level INTEGER DEFAULT 0,
    xp_bonus INTEGER DEFAULT 0,
    schedule_locked BOOLEAN DEFAULT FALSE,
    setup_edit_count INTEGER DEFAULT 0,
    last_edit_date TEXT,
    last_active_at TIMESTAMP WITH TIME ZONE,
    quizzes_completed INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Daily micro-tasks
CREATE TABLE IF NOT EXISTS tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id UUID REFERENCES students(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    subject TEXT,
    description TEXT,
    status TEXT DEFAULT 'pending',
    due_date TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Daily activity tracking
CREATE TABLE IF NOT EXISTS daily_activity (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id UUID REFERENCES students(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    study_hours NUMERIC DEFAULT 0,
    tasks_completed INTEGER DEFAULT 0,
    tasks_total INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(student_id, date)
);

-- Interaction tracking
CREATE TABLE IF NOT EXISTS interactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id UUID REFERENCES students(id) ON DELETE CASCADE,
    direction TEXT NOT NULL,
    message_type TEXT,
    platform TEXT DEFAULT 'whatsapp',
    content TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- AI-generated quizzes
CREATE TABLE IF NOT EXISTS quizzes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id UUID REFERENCES students(id) ON DELETE CASCADE,
    subject TEXT,
    topic TEXT,
    questions JSONB,
    total_questions INTEGER DEFAULT 10,
    student_answers JSONB,
    score INTEGER,
    percentage NUMERIC,
    passed BOOLEAN,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    answered_at TIMESTAMP WITH TIME ZONE
);
