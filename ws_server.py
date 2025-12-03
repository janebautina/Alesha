import asyncio
import websockets
import json
#depricated
connected_clients = set()

async def handler(websocket):  # path removed correctly
    print("🔌 New client connected")
    connected_clients.add(websocket)
    try:
        while True:
            await asyncio.sleep(10)
    except websockets.exceptions.ConnectionClosed:
        print("❌ Client disconnected")
    finally:
        connected_clients.remove(websocket)

async def broadcast_message(message_dict):
    if connected_clients:
        message = json.dumps(message_dict)
        print(f"📡 Broadcasting to {len(connected_clients)} clients: {message}")
        await asyncio.gather(
            *(client.send(message) for client in connected_clients),
            return_exceptions=True
        )
    else:
        print("⚠️ No connected clients to broadcast to.")

async def main():
    print("🚀 WebSocket server running on ws://localhost:8765")
    async with websockets.serve(handler, "localhost", 8765):
        await asyncio.Future()  # Run forever

if __name__ == "__main__":
    asyncio.run(main())
