"use client";

import { useEffect, useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";

interface ChatMessage {
  id: string;
  author: string;
  content: string;
  language: string;
}

export default function HomePage() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");

  useEffect(() => {
    const ws = new WebSocket("ws://localhost:8765");

    ws.onopen = () => {
      console.log("✅ Connected to WebSocket server");
    };

    ws.onmessage = (event) => {
      try {
        const data: ChatMessage = JSON.parse(event.data);
        console.log("📥 New message:", data);
        setMessages((prev) => [...prev.slice(-49), data]); // Keep last 50
      } catch (err) {
        console.error("❌ Error parsing WebSocket message:", err);
      }
    };

    ws.onerror = (err) => {
      console.error("❌ WebSocket error", err);
    };

    ws.onclose = () => {
      console.warn("⚠️ WebSocket connection closed");
    };

    return () => {
      ws.close();
    };
  }, []);

  return (
    <main className="min-h-screen bg-gray-50 p-4 sm:p-6">
      <h1 className="text-xl sm:text-2xl font-bold mb-4">📺 Live Chat Viewer (Alesha)</h1>

      <ScrollArea className="h-[65vh] border rounded-lg bg-white p-3 shadow">
        <div className="space-y-4">
          {messages.length === 0 && <p className="text-gray-500">Waiting for messages...</p>}
          {messages.map((msg) => (
            <Card key={msg.id} className="border shadow-sm">
              <CardContent className="p-3">
                <p className="text-sm font-medium">👤 {msg.author}</p>
                <p className="text-base mt-1">💬 {msg.content}</p>
                <p className="text-xs text-gray-400 mt-2">🌐 {msg.language}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      </ScrollArea>

      <div className="mt-4 flex gap-2">
        <Input
          placeholder="Type a manual reply (not connected yet)"
          value={input}
          onChange={(e) => setInput(e.target.value)}
        />
        <Button disabled>Send</Button>
      </div>
    </main>
  );
}
