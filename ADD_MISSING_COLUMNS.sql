-- Run ALL of these in Supabase SQL Editor:
-- https://supabase.com/dashboard/project/dvrdvdnxvnattcjqosdw/sql/new

ALTER TABLE students ADD COLUMN IF NOT EXISTS guardian_email TEXT;
ALTER TABLE students ADD COLUMN IF NOT EXISTS student_email TEXT;
ALTER TABLE students ADD COLUMN IF NOT EXISTS setup_edit_count INTEGER DEFAULT 0;
ALTER TABLE students ADD COLUMN IF NOT EXISTS last_edit_date TEXT;
ALTER TABLE students ADD COLUMN IF NOT EXISTS quizzes_completed INTEGER DEFAULT 0;
