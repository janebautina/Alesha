import asyncio
import websockets
import json

connected_clients = set()

async def handler(websocket):  # remove `, path`
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
        await asyncio.wait([client.send(message) for client in connected_clients])

async def main():
    print("🚀 WebSocket server running on ws://localhost:8765")
    async with websockets.serve(handler, "localhost", 8765):
        await asyncio.Future()  # Run forever

if __name__ == "__main__":
    asyncio.run(main())
