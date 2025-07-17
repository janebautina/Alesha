-- Create messages table for storing chat messages
CREATE TABLE IF NOT EXISTS messages (
    id SERIAL PRIMARY KEY,
    message_id TEXT UNIQUE NOT NULL,
    author TEXT NOT NULL,
    content TEXT NOT NULL,
    language TEXT,
    timestamp DOUBLE PRECISION NOT NULL,
    platform TEXT DEFAULT 'youtube',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create index for faster queries
CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp);
CREATE INDEX IF NOT EXISTS idx_messages_author ON messages(author);
CREATE INDEX IF NOT EXISTS idx_messages_language ON messages(language);

-- Enable Row Level Security (RLS)
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;

-- Create policy to allow all operations (you can restrict this based on your needs)
CREATE POLICY "Allow all operations on messages" ON messages
    FOR ALL USING (true); 