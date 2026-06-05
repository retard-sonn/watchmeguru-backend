-- Phase 3 Migration: Add country tracking + setup_complete + fix quizzes
-- Run in Supabase SQL Editor

ALTER TABLE students ADD COLUMN IF NOT EXISTS country TEXT DEFAULT 'IN';
ALTER TABLE students ADD COLUMN IF NOT EXISTS country_code TEXT DEFAULT 'IN';
ALTER TABLE students ADD COLUMN IF NOT EXISTS isd_code TEXT DEFAULT '+91';
ALTER TABLE students ADD COLUMN IF NOT EXISTS setup_complete BOOLEAN DEFAULT FALSE;

-- Fix quizzes table for new schema
ALTER TABLE quizzes ADD COLUMN IF NOT EXISTS subject TEXT;
ALTER TABLE quizzes ADD COLUMN IF NOT EXISTS topic TEXT;
ALTER TABLE quizzes ADD COLUMN IF NOT EXISTS questions JSONB;
ALTER TABLE quizzes ADD COLUMN IF NOT EXISTS student_answers JSONB;
ALTER TABLE quizzes ADD COLUMN IF NOT EXISTS total_questions INTEGER DEFAULT 10;
ALTER TABLE quizzes ADD COLUMN IF NOT EXISTS percentage NUMERIC;
ALTER TABLE quizzes ADD COLUMN IF NOT EXISTS passed BOOLEAN;
ALTER TABLE quizzes ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'pending';

-- Add session topic tracking
ALTER TABLE tasks ADD COLUMN IF NOT EXISTS topic TEXT;
ALTER TABLE tasks ADD COLUMN IF NOT EXISTS subtopic TEXT;
