from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from carla_vehicle import CarlaController
import asyncio
import json
import time
from datetime import datetime

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:8080"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/robots/{robot_id}/spawn")
async def spawn_vehicle(
    robot_id: str,
    x: float = Query(...),
    y: float = Query(...),
    z: float = Query(...)
):
    controller = CarlaController.get_instance(robot_id)
    result= controller.spawn_vehicle(x, y, z)
    if result is None:
        raise HTTPException(status_code=500, detail="Failed to spawn vehicle")
    print(result)
    return {"message": result}

@app.post("/robots/{robot_id}/destroy_vehicle")
async def destroy_vehicle(robot_id: str):
    controller = CarlaController.get_instance(robot_id)
    return {"message": controller.destroy_vehicle()}

@app.post("/robots/{robot_id}/start_drive")
async def start_drive(
    robot_id: str,
    x: float = Query(...),
    y: float = Query(...),
    z: float = Query(...)
):
    controller = CarlaController.get_instance(robot_id)
    return {"message": controller.start_drive(x, y, z)}

@app.post("/robots/{robot_id}/stop_drive")
async def stop_drive(robot_id: str):
    controller = CarlaController.get_instance(robot_id)
    return {"message": controller.stop_drive()}

@app.get("/robots/{robot_id}/stream_data")
async def telemetry_stream(robot_id: str):
    controller = CarlaController.get_instance(robot_id)
    
    async def event_generator():
        while True:
            data = controller.get_telemetry()
            if data:
                data['timestamp'] = datetime.now().isoformat()
                yield f"data: {json.dumps(data)}\n\n"
            await asyncio.sleep(0.05)
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={'Cache-Control': 'no-cache'}
    )

# @app.get("/robots/{robot_id}/video_feed")
# def video_stream(robot_id: str):
#     controller = CarlaController.get_instance(robot_id)

#     def frame_generator():
#         while True:
#             frame = controller.get_current_frame()
#             if frame:
#                 yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
#             time.sleep(0.05)
    
#     return StreamingResponse(
#         frame_generator(),
#         media_type="multipart/x-mixed-replace; boundary=frame"
#     )

@app.get("/robots/{robot_id}/video_feed")
def robot_video_feed(robot_id: str):
    controller = CarlaController.get_instance(robot_id)
    
    def frame_generator():
        frame_count = 0
        while True:
            frame = controller.get_current_frame()
            if frame:
                yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
                frame_count = 0  # Reset counter on successful frame
            else:
                frame_count += 1
                if frame_count > 100:  # ~10 seconds timeout
                    break
                time.sleep(0.1)
    
    return StreamingResponse(
        frame_generator(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )

@app.post("/robots/{robot_id}/attach_camera")
def attach_robot_camera(robot_id: str):
    controller = CarlaController.get_instance(robot_id)
    return {"message": controller.attach_camera()}


@app.post("/robots/{robot_id}/detach_camera")
def detach_robot_camera(robot_id: str):
    controller = CarlaController.get_instance(robot_id)
    return {"message": controller.detach_camera()}


@app.post("/robots/{robot_id}/start_streaming")
def start_robot_streaming(robot_id: str):
    controller = CarlaController.get_instance(robot_id)
    return {"message": controller.start_streaming()}

@app.post("/robots/{robot_id}/stop_streaming")
def stop_robot_streaming(robot_id: str):
    controller = CarlaController.get_instance(robot_id)
    return {"message": controller.stop_streaming()}