import { NextResponse } from "next/server";

export async function GET() {
  try {
    const res = await fetch("http://localhost:3001/messages");

    if (!res.ok) {
      return NextResponse.json({ error: "Failed to fetch messages" }, { status: 500 });
    }

    const data = await res.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error("API fetch error:", error);
    return NextResponse.json({ error: "Internal Server Error" }, { status: 500 });
  }
}