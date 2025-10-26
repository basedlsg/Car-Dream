"""
CARLA REST API wrapper service.
Provides FastAPI endpoints for CARLA simulation control and Pub/Sub event publishing.
"""

import asyncio
import logging
import os
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
from contextlib import asynccontextmanager

import carla
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from google.cloud import pubsub_v1
import json

from state_manager import StateManager, HealthMonitor, SimulationStatus
from error_handler import ErrorHandler, ErrorType

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
CARLA_HOST = os.environ.get('CARLA_HOST', 'localhost')
CARLA_PORT = int(os.environ.get('CARLA_PORT', '2000'))
PROJECT_ID = os.environ.get('GOOGLE_CLOUD_PROJECT', 'your-project-id')
PUBSUB_TOPIC = os.environ.get('PUBSUB_TOPIC', 'simulation-events')

# Global variables
carla_client = None
publisher = None
active_simulations: Dict[str, Dict] = {}
state_manager = None
health_monitor = None
error_handler = None


class SimulationConfig(BaseModel):
    """Configuration for starting a simulation."""
    scenario_name: str = "default"
    map_name: str = "Town01"
    weather_conditions: Dict[str, Any] = {
        "cloudiness": 0.0,
        "precipitation": 0.0,
        "sun_altitude_angle": 70.0
    }
    spawn_point: Optional[Dict[str, float]] = None
    vehicle_type: str = "vehicle.tesla.model3"


class SimulationAction(BaseModel):
    """Action to execute in simulation."""
    steering: float = 0.0  # -1.0 to 1.0
    throttle: float = 0.0  # 0.0 to 1.0
    brake: float = 0.0     # 0.0 to 1.0
    gear: int = 1
    hand_brake: bool = False
    reverse: bool = False


class SimulationState(BaseModel):
    """Current state of simulation."""
    simulation_id: str
    timestamp: datetime
    vehicle_position: Dict[str, float]
    vehicle_velocity: Dict[str, float]
    vehicle_acceleration: Dict[str, float]
    vehicle_rotation: Dict[str, float]
    sensor_data: Dict[str, Any]
    traffic_state: Dict[str, Any]
    weather_state: Dict[str, Any]


class CarlaSimulationManager:
    """Manages CARLA simulation instances."""
    
    def __init__(self):
        self.client = None
        self.world = None
        self.vehicles = {}
        self.sensors = {}
    
    async def connect(self):
        """Connect to CARLA server."""
        try:
            self.client = carla.Client(CARLA_HOST, CARLA_PORT)
            self.client.set_timeout(10.0)
            self.world = self.client.get_world()
            logger.info(f"Connected to CARLA server at {CARLA_HOST}:{CARLA_PORT}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to CARLA: {e}")
            return False
    
    def create_simulation(self, config: SimulationConfig) -> str:
        """Create a new simulation instance."""
        simulation_id = str(uuid.uuid4())
        
        try:
            # Load the specified map
            if config.map_name != self.world.get_map().name:
                logger.info(f"Loading map: {config.map_name}")
                self.client.load_world(config.map_name)
                self.world = self.client.get_world()
            
            # Set weather conditions
            weather = carla.WeatherParameters(
                cloudiness=config.weather_conditions.get("cloudiness", 0.0),
                precipitation=config.weather_conditions.get("precipitation", 0.0),
                sun_altitude_angle=config.weather_conditions.get("sun_altitude_angle", 70.0)
            )
            self.world.set_weather(weather)
            
            # Spawn vehicle
            blueprint_library = self.world.get_blueprint_library()
            vehicle_bp = blueprint_library.find(config.vehicle_type)
            
            # Get spawn point
            if config.spawn_point:
                spawn_point = carla.Transform(
                    carla.Location(
                        x=config.spawn_point.get("x", 0),
                        y=config.spawn_point.get("y", 0),
                        z=config.spawn_point.get("z", 0.3)
                    )
                )
            else:
                spawn_points = self.world.get_map().get_spawn_points()
                spawn_point = spawn_points[0] if spawn_points else carla.Transform()
            
            # Spawn the vehicle
            vehicle = self.world.spawn_actor(vehicle_bp, spawn_point)
            self.vehicles[simulation_id] = vehicle
            
            # Set up basic sensors (camera, lidar, etc.)
            self._setup_sensors(simulation_id, vehicle)
            
            # Create initial checkpoint
            if state_manager:
                state_manager.create_checkpoint(simulation_id, vehicle, self.world)
            
            # Store simulation info
            active_simulations[simulation_id] = {
                "config": config.dict(),
                "created_at": datetime.now(),
                "status": SimulationStatus.RUNNING.value,
                "vehicle_id": vehicle.id
            }
            
            logger.info(f"Created simulation {simulation_id}")
            return simulation_id
            
        except Exception as e:
            logger.error(f"Failed to create simulation: {e}")
            
            # Handle error through error handler
            if error_handler:
                asyncio.create_task(error_handler.handle_error(
                    simulation_id,
                    ErrorType.SIMULATION_ERROR,
                    str(e),
                    {"stack_trace": str(e)}
                ))
            
            raise HTTPException(status_code=500, detail=f"Failed to create simulation: {e}")
    
    def _setup_sensors(self, simulation_id: str, vehicle):
        """Set up sensors for the vehicle."""
        blueprint_library = self.world.get_blueprint_library()
        
        # RGB Camera
        camera_bp = blueprint_library.find('sensor.camera.rgb')
        camera_bp.set_attribute('image_size_x', '800')
        camera_bp.set_attribute('image_size_y', '600')
        camera_transform = carla.Transform(carla.Location(x=2.0, z=1.4))
        camera = self.world.spawn_actor(camera_bp, camera_transform, attach_to=vehicle)
        
        # Store sensor reference
        if simulation_id not in self.sensors:
            self.sensors[simulation_id] = {}
        self.sensors[simulation_id]['camera'] = camera
    
    def get_simulation_state(self, simulation_id: str) -> SimulationState:
        """Get current state of simulation."""
        if simulation_id not in self.vehicles:
            raise HTTPException(status_code=404, detail="Simulation not found")
        
        vehicle = self.vehicles[simulation_id]
        transform = vehicle.get_transform()
        velocity = vehicle.get_velocity()
        acceleration = vehicle.get_acceleration()
        
        # Get traffic information
        traffic_manager = self.client.get_trafficmanager()
        
        state = SimulationState(
            simulation_id=simulation_id,
            timestamp=datetime.now(),
            vehicle_position={
                "x": transform.location.x,
                "y": transform.location.y,
                "z": transform.location.z
            },
            vehicle_velocity={
                "x": velocity.x,
                "y": velocity.y,
                "z": velocity.z
            },
            vehicle_acceleration={
                "x": acceleration.x,
                "y": acceleration.y,
                "z": acceleration.z
            },
            vehicle_rotation={
                "pitch": transform.rotation.pitch,
                "yaw": transform.rotation.yaw,
                "roll": transform.rotation.roll
            },
            sensor_data={
                "camera_available": simulation_id in self.sensors and 'camera' in self.sensors[simulation_id]
            },
            traffic_state={
                "nearby_vehicles": len([v for v in self.world.get_actors().filter('vehicle.*') if v.id != vehicle.id])
            },
            weather_state={
                "cloudiness": self.world.get_weather().cloudiness,
                "precipitation": self.world.get_weather().precipitation,
                "sun_altitude_angle": self.world.get_weather().sun_altitude_angle
            }
        )
        
        return state
    
    def execute_action(self, simulation_id: str, action: SimulationAction) -> Dict[str, Any]:
        """Execute an action in the simulation."""
        if simulation_id not in self.vehicles:
            raise HTTPException(status_code=404, detail="Simulation not found")
        
        vehicle = self.vehicles[simulation_id]
        
        # Create control object
        control = carla.VehicleControl(
            throttle=action.throttle,
            steer=action.steering,
            brake=action.brake,
            hand_brake=action.hand_brake,
            reverse=action.reverse,
            manual_gear_shift=True,
            gear=action.gear
        )
        
        # Apply control
        vehicle.apply_control(control)
        
        # Get new state after action
        new_state = self.get_simulation_state(simulation_id)
        
        return {
            "action_applied": action.dict(),
            "new_state": new_state.dict(),
            "timestamp": datetime.now().isoformat()
        }
    
    def cleanup_simulation(self, simulation_id: str) -> Dict[str, str]:
        """Clean up simulation resources."""
        try:
            # Destroy vehicle
            if simulation_id in self.vehicles:
                self.vehicles[simulation_id].destroy()
                del self.vehicles[simulation_id]
            
            # Destroy sensors
            if simulation_id in self.sensors:
                for sensor in self.sensors[simulation_id].values():
                    sensor.destroy()
                del self.sensors[simulation_id]
            
            # Remove from active simulations
            if simulation_id in active_simulations:
                del active_simulations[simulation_id]
            
            logger.info(f"Cleaned up simulation {simulation_id}")
            return {"status": "cleaned_up", "simulation_id": simulation_id}
            
        except Exception as e:
            logger.error(f"Error cleaning up simulation {simulation_id}: {e}")
            return {"status": "error", "message": str(e)}


# Initialize simulation manager
sim_manager = CarlaSimulationManager()


async def publish_event(event_type: str, data: Dict[str, Any]):
    """Publish event to Pub/Sub."""
    if publisher is None:
        return
    
    try:
        message_data = {
            "event_type": event_type,
            "timestamp": datetime.now().isoformat(),
            "data": data
        }
        
        # Publish message
        future = publisher.publish(
            f"projects/{PROJECT_ID}/topics/{PUBSUB_TOPIC}",
            json.dumps(message_data).encode('utf-8')
        )
        
        logger.info(f"Published event: {event_type}")
        
    except Exception as e:
        logger.error(f"Failed to publish event: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management."""
    global carla_client, publisher, state_manager, health_monitor, error_handler
    
    # Startup
    logger.info("Starting CARLA REST API service...")
    
    # Initialize state management
    state_manager = StateManager()
    health_monitor = HealthMonitor()
    error_handler = ErrorHandler(state_manager, health_monitor)
    
    # Connect to CARLA with error handling
    try:
        if not await sim_manager.connect():
            logger.error("Failed to connect to CARLA server")
            # Attempt recovery
            await error_handler.handle_error(
                "system", 
                ErrorType.CARLA_CRASH, 
                "Initial CARLA connection failed"
            )
    except Exception as e:
        logger.error(f"CARLA connection error: {e}")
        await error_handler.handle_error(
            "system", 
            ErrorType.CARLA_CRASH, 
            str(e)
        )
    
    # Initialize Pub/Sub publisher
    try:
        publisher = pubsub_v1.PublisherClient()
        logger.info("Initialized Pub/Sub publisher")
    except Exception as e:
        logger.warning(f"Could not initialize Pub/Sub publisher: {e}")
    
    # Start periodic health monitoring
    asyncio.create_task(periodic_health_monitoring())
    
    yield
    
    # Shutdown
    logger.info("Shutting down CARLA REST API service...")
    
    # Clean up all active simulations
    for simulation_id in list(active_simulations.keys()):
        try:
            sim_manager.cleanup_simulation(simulation_id)
        except Exception as e:
            logger.error(f"Error cleaning up simulation {simulation_id}: {e}")


async def periodic_health_monitoring():
    """Periodic health monitoring task."""
    while True:
        try:
            if error_handler and sim_manager.client:
                await error_handler.periodic_health_check(
                    sim_manager.client, 
                    active_simulations
                )
        except Exception as e:
            logger.error(f"Health monitoring error: {e}")
        
        # Wait 30 seconds before next check
        await asyncio.sleep(30)


# Create FastAPI app
app = FastAPI(
    title="CARLA REST API",
    description="REST API wrapper for CARLA simulation control",
    version="1.0.0",
    lifespan=lifespan
)
#
 API Endpoints

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    try:
        # Check CARLA connection
        carla_status = "connected" if sim_manager.client else "disconnected"
        
        # Get detailed health status if health monitor is available
        health_status = {}
        if health_monitor:
            health_status = health_monitor.get_health_status()
        
        return {
            "status": health_status.get("status", "unknown"),
            "carla_status": carla_status,
            "active_simulations": len(active_simulations),
            "health_details": health_status,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Service unhealthy: {e}")


@app.get("/health/detailed")
async def detailed_health_check():
    """Detailed health check with metrics and error history."""
    try:
        health_status = {}
        error_history = []
        recovery_status = {}
        
        if health_monitor:
            health_status = health_monitor.get_health_status()
        
        if state_manager:
            error_history = [
                {
                    "timestamp": error.timestamp.isoformat(),
                    "simulation_id": error.simulation_id,
                    "error_type": error.error_type,
                    "error_message": error.error_message,
                    "recovery_attempted": error.recovery_attempted,
                    "recovery_successful": error.recovery_successful
                }
                for error in state_manager.get_error_history(hours=24)
            ]
        
        if error_handler:
            recovery_status = {
                sim_id: error_handler.get_recovery_status(sim_id)
                for sim_id in active_simulations.keys()
            }
        
        return {
            "health_status": health_status,
            "error_history": error_history,
            "recovery_status": recovery_status,
            "active_simulations": active_simulations,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get detailed health: {e}")


@app.get("/metrics")
async def get_metrics():
    """Get system metrics and performance data."""
    try:
        metrics = {}
        
        if health_monitor:
            # Get resource usage
            resources = health_monitor.check_resource_usage()
            metrics.update(resources)
            
            # Get error rate
            if state_manager:
                error_history = state_manager.get_error_history(hours=1)
                error_rate = health_monitor.calculate_error_rate(error_history)
                metrics["error_rate"] = error_rate
        
        # Add simulation metrics
        metrics.update({
            "active_simulations_count": len(active_simulations),
            "total_checkpoints": len(state_manager.checkpoints) if state_manager else 0,
            "carla_restart_count": error_handler.carla_restart_count if error_handler else 0
        })
        
        return {
            "metrics": metrics,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get metrics: {e}")


@app.post("/simulation/start")
async def start_simulation(
    config: SimulationConfig,
    background_tasks: BackgroundTasks
):
    """Start a new CARLA simulation."""
    try:
        simulation_id = sim_manager.create_simulation(config)
        
        # Publish simulation started event
        background_tasks.add_task(
            publish_event,
            "simulation.started",
            {
                "simulation_id": simulation_id,
                "config": config.dict()
            }
        )
        
        return {
            "simulation_id": simulation_id,
            "status": "started",
            "config": config.dict(),
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to start simulation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/simulation/{simulation_id}/state")
async def get_simulation_state(simulation_id: str):
    """Get current state of simulation."""
    try:
        state = sim_manager.get_simulation_state(simulation_id)
        return state.dict()
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get simulation state: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/simulation/{simulation_id}/action")
async def execute_action(
    simulation_id: str,
    action: SimulationAction,
    background_tasks: BackgroundTasks
):
    """Execute an action in the simulation."""
    try:
        result = sim_manager.execute_action(simulation_id, action)
        
        # Publish action executed event
        background_tasks.add_task(
            publish_event,
            "action.executed",
            {
                "simulation_id": simulation_id,
                "action": action.dict(),
                "result": result
            }
        )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to execute action: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/simulation/{simulation_id}")
async def cleanup_simulation(
    simulation_id: str,
    background_tasks: BackgroundTasks
):
    """Clean up simulation resources."""
    try:
        result = sim_manager.cleanup_simulation(simulation_id)
        
        # Publish simulation ended event
        background_tasks.add_task(
            publish_event,
            "simulation.ended",
            {
                "simulation_id": simulation_id,
                "cleanup_result": result
            }
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to cleanup simulation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/simulations")
async def list_simulations():
    """List all active simulations."""
    return {
        "active_simulations": active_simulations,
        "count": len(active_simulations),
        "timestamp": datetime.now().isoformat()
    }


@app.get("/simulation/{simulation_id}/info")
async def get_simulation_info(simulation_id: str):
    """Get simulation information."""
    if simulation_id not in active_simulations:
        raise HTTPException(status_code=404, detail="Simulation not found")
    
    return active_simulations[simulation_id]


@app.post("/simulation/{simulation_id}/reset")
async def reset_simulation(
    simulation_id: str,
    background_tasks: BackgroundTasks
):
    """Reset simulation to initial state."""
    try:
        if simulation_id not in active_simulations:
            raise HTTPException(status_code=404, detail="Simulation not found")
        
        # Get original config
        original_config = active_simulations[simulation_id]["config"]
        
        # Cleanup current simulation
        sim_manager.cleanup_simulation(simulation_id)
        
        # Create new simulation with same config
        new_simulation_id = sim_manager.create_simulation(SimulationConfig(**original_config))
        
        # Publish reset event
        background_tasks.add_task(
            publish_event,
            "simulation.reset",
            {
                "old_simulation_id": simulation_id,
                "new_simulation_id": new_simulation_id
            }
        )
        
        return {
            "old_simulation_id": simulation_id,
            "new_simulation_id": new_simulation_id,
            "status": "reset",
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to reset simulation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)