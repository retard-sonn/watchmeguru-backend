-- Run these in Supabase SQL Editor:
-- https://supabase.com/dashboard/project/dvrdvdnxvnattcjqosdw/sql/new

ALTER TABLE students ADD COLUMN IF NOT EXISTS guardian_email TEXT;
ALTER TABLE students ADD COLUMN IF NOT EXISTS student_email TEXT;
