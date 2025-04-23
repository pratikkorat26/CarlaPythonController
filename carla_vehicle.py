import random
import carla
import threading
import time
import math
import cv2
import numpy as np
from queue import Queue


class CarlaController:
    _instances = {}  # Dictionary to store controller instances by robot_id

    @classmethod
    def get_instance(cls, robot_id):
        """Get or create CarlaController instance for specific robot"""
        if robot_id not in cls._instances:
            controller = cls(robot_id)
            if controller.initialized:
                cls._instances[robot_id] = controller
            else:
                raise RuntimeError("Failed to initialize CARLA connection. Is the simulator running?")
        return cls._instances[robot_id]

    @classmethod
    def destroy_instance(cls, robot_id):
        """Destroy the instance for specified robot"""
        if robot_id in cls._instances:
            cls._instances[robot_id].cleanup()
            del cls._instances[robot_id]
            return f"Controller for robot {robot_id} destroyed successfully"
        return f"No controller for robot {robot_id} exists"

    def __init__(self, robot_id):
        self.robot_id = robot_id
        self.initialized = False
        self.vehicle = None
        self.camera = None
        self.current_frame = None
        self.camera_lock = threading.Lock()
        self.telemetry_data = {}
        self.telemetry_lock = threading.Lock()
        self.frame_queue = Queue(maxsize=20)
        self.telemetry_running = False
        self.detection_running = False
        self.navigation_running = False

        try:
            self.client = carla.Client('localhost', 2000)
            self.client.set_timeout(5.0)  # Reduced timeout
            # Check connection before proceeding
            try:
                self.world = self.client.get_world()
                self.map = self.world.get_map()
                self.bp_lib = self.world.get_blueprint_library()
                self.initialized = True
                print(f"🚗 Initialized CarlaController for robot {robot_id}")
            except Exception as e:
                print(f"❌ Failed to connect to CARLA: {e}")
                # Set these to None so we can identify the failed state
                self.world = None
                self.map = None
                self.bp_lib = None
        except Exception as e:
            print(f"❌ Failed to initialize CARLA client: {e}")

    def cleanup(self):
        """Clean up all resources"""
        print(f"🚗 Cleaning up CarlaController for robot {self.robot_id}")
        self.stop_drive()
        self.stop_telemetry()
        self.stop_detection()

        # Detach camera before destroying vehicle
        self.detach_camera()

        # Add delay to ensure camera is fully detached
        time.sleep(0.2)

        if self.vehicle:
            try:
                self.vehicle.destroy()
            except Exception as e:
                print(f"❌ Error destroying vehicle: {e}")
            self.vehicle = None

    def spawn_vehicle(self, x=None, y=None, z=None):
        if self.vehicle:
            return "Vehicle already spawned."

        # Get list of available blueprints. Adjust filter if necessary.
        blueprints = self.bp_lib.filter("vehicle.tesla.model3")
        if not blueprints:
            return "No matching blueprint found."
        blueprint = blueprints[0]

        spawn_points = self.map.get_spawn_points()
        print(f"Available spawn points: {len(spawn_points)}")
        if not spawn_points:
            return "No spawn points available on the map."

        # If coordinates provided, try to use that transform first
        if x is not None and y is not None and z is not None:
            transform = carla.Transform(carla.Location(x=x, y=y, z=z))
            self.vehicle = self.world.try_spawn_actor(blueprint, transform)
            if self.vehicle:
                return f"Vehicle spawned at {transform.location}"

        # Otherwise, try each available spawn point until one succeeds
        for transform in random.sample(spawn_points, len(spawn_points)):
            self.vehicle = self.world.try_spawn_actor(blueprint, transform)
            if self.vehicle:
                return f"Vehicle spawned at {transform.location}"

        return "Failed to spawn vehicle from all available spawn points."

    def destroy_vehicle(self):
        self.stop_drive()
        self.stop_telemetry()
        self.stop_detection()
        self.detach_camera()
        if self.vehicle:
            self.vehicle.destroy()
            self.vehicle = None
            return "Vehicle destroyed."
        return "No vehicle to destroy."

    def start_drive(self, x, y, z):
        if not self.vehicle:
            return "No vehicle spawned."

        def drive_loop():
            self.navigation_running = True
            dest = carla.Location(x=x, y=y, z=z)

            while self.navigation_running:
                # Get current location and distance to target
                current = self.vehicle.get_location()
                distance = current.distance(dest)

                if distance < 2.0:
                    # Arrived at destination
                    control = carla.VehicleControl(throttle=0.0, brake=1.0)
                    self.vehicle.apply_control(control)
                    break

                # Get next waypoint toward destination
                next_wp = self.map.get_waypoint(current)
                target_wp = self.map.get_waypoint(dest)

                # Apply vehicle control
                control = carla.VehicleControl()

                # Simple speed control based on distance
                desired_speed = min(30.0, distance * 3.0)
                current_speed = self.vehicle.get_velocity().length() * 3.6  # km/h

                if current_speed < desired_speed:
                    control.throttle = 0.7
                    control.brake = 0.0
                else:
                    control.throttle = 0.0
                    control.brake = 0.5

                # Apply steering based on waypoint direction
                self.vehicle.apply_control(control)
                time.sleep(0.1)

            self.navigation_running = False

        threading.Thread(target=drive_loop, daemon=True).start()
        return f"Driving to {x},{y},{z}"

    def stop_drive(self):
        self.navigation_running = False
        return "Drive stopped."

    def start_telemetry(self):
        if not self.vehicle or self.telemetry_running:
            return "Telemetry already running or no vehicle."

        def telemetry_loop():
            self.telemetry_running = True
            while self.telemetry_running:
                t = self.vehicle.get_transform()
                v = self.vehicle.get_velocity()
                c = self.vehicle.get_control()  # Get control data
                speed = math.sqrt(v.x ** 2 + v.y ** 2 + v.z ** 2)
                with self.telemetry_lock:
                    self.telemetry_data = {
                        "x": t.location.x,
                        "y": t.location.y,
                        "z": t.location.z,
                        "yaw": t.rotation.yaw,
                        "speed": speed * 3.6,
                        "vehicle_id": self.vehicle.id,
                        "vehicle_type": self.vehicle.type_id,
                        "throttle": c.throttle,  # 0-1 value
                        "steering": c.steer,  # -1 to 1 value
                        "brake": c.brake,  # 0-1 value
                    }
                time.sleep(0.2)

        threading.Thread(target=telemetry_loop, daemon=True).start()
        return "Telemetry started."

    def stop_telemetry(self):
        self.telemetry_running = False
        return "Telemetry stopped."

    def get_telemetry(self):
        if not self.vehicle:
            return None
            
        velocity = self.vehicle.get_velocity()
        control = self.vehicle.get_control()
        
        return {
            "speed": math.sqrt(velocity.x**2 + velocity.y**2 + velocity.z**2) * 3.6,  # km/h
            "throttle": control.throttle,
            "steering": control.steer,
            "brake": control.brake,
            "x": self.vehicle.get_location().x,
            "y": self.vehicle.get_location().y,
            "z": self.vehicle.get_location().z
        }

    # def start_streaming(self):
    #     if not self.camera:
    #         return "❌ No camera attached."

    #     def _on_image(image):
    #         try:
    #             # Only process if we're still streaming
    #             if self.camera and hasattr(image, 'raw_data'):
    #                 array = np.frombuffer(image.raw_data, dtype=np.uint8).reshape((image.height, image.width, 4))[:, :,
    #                         :3]
    #                 _, buffer = cv2.imencode('.jpg', array)
    #                 with self.camera_lock:
    #                     self.current_frame = buffer.tobytes()
    #                 if not self.frame_queue.full():
    #                     self.frame_queue.put(array)
    #         except Exception as e:
    #             print(f"❌ Frame processing error: {e}")

    #     try:
    #         self.camera.listen(_on_image)
    #         return "✅ Camera streaming started."
    #     except Exception as e:
    #         print(f"❌ Failed to start camera: {e}")
    #         return f"❌ Camera streaming failed: {e}"

    def start_streaming(self):
        if not self.camera:
            return "❌ No camera attached. Attach camera first."
        
        if self.current_frame is not None:
            return "⚠️ Streaming already active"

        def _on_image(image):
            try:
                array = np.frombuffer(image.raw_data, dtype=np.uint8)
                array = array.reshape((image.height, image.width, 4))[:, :, :3]
                _, buffer = cv2.imencode('.jpg', array)
                with self.camera_lock:
                    self.current_frame = buffer.tobytes()
            except Exception as e:
                print(f"Frame processing error: {e}")

        try:
            self.camera.listen(_on_image)
            return "✅ Streaming started"
        except Exception as e:
            return f"❌ Streaming failed: {str(e)}"

    def stop_streaming(self):
        if self.camera:
            try:
                self.camera.stop()
                with self.camera_lock:
                    self.current_frame = None
                return "✅ Streaming stopped"
            except Exception as e:
                return f"❌ Stop streaming failed: {str(e)}"
        return "⚠️ No active stream"

    def get_current_frame(self):
        with self.camera_lock:
            return self.current_frame

    def attach_camera(self):
        if not self.vehicle:
            return "No vehicle to attach camera."

        # Clean up existing camera
        self.detach_camera()

        try:
            # Setup camera blueprint
            cam_bp = self.bp_lib.find("sensor.camera.rgb")
            cam_bp.set_attribute("image_size_x", "640")
            cam_bp.set_attribute("image_size_y", "480")
            cam_bp.set_attribute("fov", "90")

            # Position the camera
            cam_transform = carla.Transform(carla.Location(x=1.5, z=2.4))

            # Spawn camera
            self.camera = self.world.spawn_actor(cam_bp, cam_transform, attach_to=self.vehicle)
            return "✅ Camera attached."
        except Exception as e:
            print(f"❌ Error attaching camera: {e}")
            return f"❌ Camera attachment failed: {e}"

    def detach_camera(self):
        if self.camera:
            try:
                self.camera.stop()
            except Exception as e:
                print(f"⚠️ Warning while stopping camera: {e}")

            try:
                # Add small delay to ensure callback completes
                time.sleep(0.1)
                self.camera.destroy()
            except Exception as e:
                print(f"❌ Error while destroying camera: {e}")

            self.camera = None
            with self.camera_lock:
                self.current_frame = None
            # Clear queue to prevent stale data
            while not self.frame_queue.empty():
                try:
                    self.frame_queue.get_nowait()
                except:
                    pass
            return "Camera detached."
        return "No camera to detach."

    # def start_detection(self):
    #     if self.detection_running:
    #         return "Detection already running."
    #     def detect_loop():
    #         self.detection_running = True
    #         channel = grpc.insecure_channel("localhost:50051")
    #         stub = detection_pb2_grpc.YOLODetectionStub(channel)
    #         while self.detection_running:
    #             if not self.frame_queue.empty():
    #                 frame = self.frame_queue.get()
    #                 _, buffer = cv2.imencode('.jpg', frame)
    #                 request = detection_pb2.DetectionRequest(image=buffer.tobytes())
    #                 response = stub.Detect(request)
    #                 print("Detections:", [(d.label, d.confidence) for d in response.detections])
    #             else:
    #                 time.sleep(0.05)
    #         channel.close()
    #     threading.Thread(target=detect_loop, daemon=True).start()
    #     return "Detection started."

    def stop_detection(self):
        self.detection_running = False
        return "Detection stopped."