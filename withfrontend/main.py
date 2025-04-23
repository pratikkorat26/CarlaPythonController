from fastapi import FastAPI, Query, Path, HTTPException, Request
from fastapi.responses import StreamingResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
import asyncio
import json
import time

from carla_vehicle import CarlaController

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=HTMLResponse)
def dashboard():
    with open("static/index.html", encoding = "utf-8") as f:
        return f.read()


# Robot management endpoints
@app.post("/robots/{robot_id}")
def create_robot(robot_id: str):
    controller = CarlaController.get_instance(robot_id)
    return {"message": f"Robot {robot_id} created successfully"}


@app.delete("/robots/{robot_id}")
def delete_robot(robot_id: str):
    return {"message": CarlaController.destroy_instance(robot_id)}


@app.get("/robots")
def list_robots():
    return {"robots": list(CarlaController._instances.keys())}


# Robot-specific endpoints
@app.get("/robots/{robot_id}/status")
def get_robot_status(robot_id: str):
    if robot_id not in CarlaController._instances:
        raise HTTPException(status_code=404, detail=f"Robot {robot_id} not found")

    controller = CarlaController.get_instance(robot_id)
    return {
        "robot_id": robot_id,
        "vehicle": controller.vehicle is not None,
        "camera_attached": controller.camera is not None,
        "telemetry_running": controller.telemetry_running,
        "video_streaming": controller.current_frame is not None,
        "detection_running": controller.detection_running
    }


@app.post("/robots/{robot_id}/spawn")
def spawn_robot_vehicle(robot_id: str, x: float = Query(...), y: float = Query(...), z: float = Query(...)):
    if robot_id not in CarlaController._instances:
        raise HTTPException(status_code=404, detail=f"Robot {robot_id} not found")

    controller = CarlaController.get_instance(robot_id)
    return {"message": controller.spawn_vehicle(x, y, z)}


@app.post("/robots/{robot_id}/destroy_vehicle")
def destroy_robot_vehicle(robot_id: str):
    controller = CarlaController.get_instance(robot_id)
    return {"message": controller.destroy_vehicle()}


@app.post("/robots/{robot_id}/start_drive")
def start_robot_drive(robot_id: str, x: float = Query(...), y: float = Query(...), z: float = Query(...)):
    controller = CarlaController.get_instance(robot_id)
    return {"message": controller.start_drive(x, y, z)}


@app.post("/robots/{robot_id}/stop_drive")
def stop_robot_drive(robot_id: str):
    controller = CarlaController.get_instance(robot_id)
    return {"message": controller.stop_drive()}


@app.post("/robots/{robot_id}/start_telemetry")
def start_robot_telemetry(robot_id: str):
    controller = CarlaController.get_instance(robot_id)
    return {"message": controller.start_telemetry()}


@app.post("/robots/{robot_id}/stop_telemetry")
def stop_robot_telemetry(robot_id: str):
    controller = CarlaController.get_instance(robot_id)
    return {"message": controller.stop_telemetry()}


@app.get("/robots/{robot_id}/stream_data")
async def stream_robot_data(robot_id: str):
    controller = CarlaController.get_instance(robot_id)

    async def event_generator():
        while True:
            data = controller.get_telemetry()
            if data:
                yield f"data: {json.dumps(data)}\n\n"
            await asyncio.sleep(0.2)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


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


@app.get("/robots/{robot_id}/video_feed")
def robot_video_feed(robot_id: str):
    controller = CarlaController.get_instance(robot_id)

    def frame_generator():
        while True:
            frame = controller.get_current_frame()
            if frame:
                yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
            time.sleep(0.1)

    return StreamingResponse(frame_generator(), media_type="multipart/x-mixed-replace; boundary=frame")


@app.post("/robots/{robot_id}/start_detection")
def start_robot_detection(robot_id: str):
    controller = CarlaController.get_instance(robot_id)
    return {"message": controller.start_detection()}


@app.post("/robots/{robot_id}/stop_detection")
def stop_robot_detection(robot_id: str):
    controller = CarlaController.get_instance(robot_id)
    return {"message": controller.stop_detection()}


# Backward compatibility endpoints - redirect to robot-specific endpoints
@app.get("/active_robot", response_class=HTMLResponse)
def get_active_robot():
    robots = list(CarlaController._instances.keys())
    if robots:
        return robots[0]  # Return first robot
    raise HTTPException(status_code=404, detail="No robots available")


@app.post("/spawn")
async def spawn_vehicle_compat(request: Request):
    # Extract query parameters
    params = dict(request.query_params)
    robot_id = await get_active_robot_or_error()

    redirect_url = f"/robots/{robot_id}/spawn"
    if params:
        query_string = "&".join([f"{k}={v}" for k, v in params.items()])
        redirect_url += f"?{query_string}"

    return RedirectResponse(url=redirect_url, status_code=307)


@app.post("/destroy_vehicle")
async def destroy_vehicle_compat():
    robot_id = await get_active_robot_or_error()
    return RedirectResponse(url=f"/robots/{robot_id}/destroy_vehicle", status_code=307)


@app.post("/start_drive")
async def start_drive_compat(request: Request):
    params = dict(request.query_params)
    robot_id = await get_active_robot_or_error()

    redirect_url = f"/robots/{robot_id}/start_drive"
    if params:
        query_string = "&".join([f"{k}={v}" for k, v in params.items()])
        redirect_url += f"?{query_string}"

    return RedirectResponse(url=redirect_url, status_code=307)


@app.post("/stop_drive")
async def stop_drive_compat():
    robot_id = await get_active_robot_or_error()
    return RedirectResponse(url=f"/robots/{robot_id}/stop_drive", status_code=307)


@app.post("/start_telemetry")
async def start_telemetry_compat():
    robot_id = await get_active_robot_or_error()
    return RedirectResponse(url=f"/robots/{robot_id}/start_telemetry", status_code=307)


@app.post("/stop_telemetry")
async def stop_telemetry_compat():
    robot_id = await get_active_robot_or_error()
    return RedirectResponse(url=f"/robots/{robot_id}/stop_telemetry", status_code=307)


@app.get("/stream_data")
async def stream_data_compat():
    robot_id = await get_active_robot_or_error()
    return RedirectResponse(url=f"/robots/{robot_id}/stream_data", status_code=307)


@app.post("/attach_camera")
async def attach_camera_compat():
    robot_id = await get_active_robot_or_error()
    return RedirectResponse(url=f"/robots/{robot_id}/attach_camera", status_code=307)


@app.post("/detach_camera")
async def detach_camera_compat():
    robot_id = await get_active_robot_or_error()
    return RedirectResponse(url=f"/robots/{robot_id}/detach_camera", status_code=307)


@app.post("/start_streaming")
async def start_streaming_compat():
    robot_id = await get_active_robot_or_error()
    return RedirectResponse(url=f"/robots/{robot_id}/start_streaming", status_code=307)


@app.post("/stop_streaming")
async def stop_streaming_compat():
    robot_id = await get_active_robot_or_error()
    return RedirectResponse(url=f"/robots/{robot_id}/stop_streaming", status_code=307)


@app.get("/video_feed")
async def video_feed_compat():
    robot_id = await get_active_robot_or_error()
    return RedirectResponse(url=f"/robots/{robot_id}/video_feed", status_code=307)


@app.post("/start_detection")
async def start_detection_compat():
    robot_id = await get_active_robot_or_error()
    return RedirectResponse(url=f"/robots/{robot_id}/start_detection", status_code=307)


@app.post("/stop_detection")
async def stop_detection_compat():
    robot_id = await get_active_robot_or_error()
    return RedirectResponse(url=f"/robots/{robot_id}/stop_detection", status_code=307)


# Helper function
async def get_active_robot_or_error():
    robots = list(CarlaController._instances.keys())
    if not robots:
        raise HTTPException(status_code=404, detail="No robots available. Please create a robot first.")
    return robots[0]