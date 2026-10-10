-- migrations/002_add_model_name.sql
ALTER TABLE tool_call_log ADD COLUMN model_name VARCHAR(64);