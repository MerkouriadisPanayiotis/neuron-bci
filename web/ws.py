"""
NEURON — WebSocket Handler
Streams live brain data and events to React frontend clients.
"""

from fastapi import WebSocket, WebSocketDisconnect

from web.session_manager import SessionManager


async def brain_websocket(websocket: WebSocket, user_id: str, session_manager: SessionManager):
    """WebSocket endpoint for streaming brain data to a specific user's dashboard.

    Message types sent to client:
    - brain_data: Live EEG snapshot (2Hz)
    - experiment_instruction: Claude's task instruction during experiments
    - experiment_interpretation: Claude's analysis after a task
    - generation_started: A generation has been triggered
    - generation_chunk: Streaming text chunk from Claude
    - generation_complete: Generation finished with metadata
    - error: Something went wrong

    Message types received from client:
    - ping: Keep-alive
    """
    await websocket.accept()

    session = session_manager.get_session_for_user(user_id)
    if session:
        session.websocket_clients.add(websocket)

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type", "")

            if msg_type == "ping":
                await websocket.send_json({"type": "pong"})

            # Re-check session membership (session may have started after WS connected)
            current_session = session_manager.get_session_for_user(user_id)
            if current_session and websocket not in current_session.websocket_clients:
                current_session.websocket_clients.add(websocket)
                session = current_session

    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        if session:
            session.websocket_clients.discard(websocket)
