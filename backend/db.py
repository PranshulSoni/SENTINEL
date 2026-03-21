from motor.motor_asyncio import AsyncIOMotorClient
from config import get_settings
import logging

logger = logging.getLogger(__name__)

client: AsyncIOMotorClient = None
db = None

# Collection references (set after connect)
incidents = None
feed_snapshots = None
llm_outputs = None
chat_history = None
signal_baselines = None
diversion_routes = None
cctv_events = None
congestion_zones = None
intersections = None
road_segments = None


async def connect_db():
    global client, db, incidents, feed_snapshots, llm_outputs, chat_history
    global signal_baselines, diversion_routes, cctv_events, congestion_zones
    global intersections, road_segments

    settings = get_settings()

    try:
        client = AsyncIOMotorClient(
            settings.mongodb_uri,
            serverSelectionTimeoutMS=5000,
        )
        # Ping to verify connectivity
        await client.admin.command("ping")

        db = client[settings.mongodb_db_name]

        # Collection references
        incidents = db["incidents"]
        feed_snapshots = db["feed_snapshots"]
        llm_outputs = db["llm_outputs"]
        chat_history = db["chat_history"]
        signal_baselines = db["signal_baselines"]
        diversion_routes = db["diversion_routes"]
        cctv_events = db["cctv_events"]
        congestion_zones = db["congestion_zones"]
        intersections = db["intersections"]
        road_segments = db["road_segments"]

        # Create indexes
        await incidents.create_index([("city", 1), ("status", 1)])
        await incidents.create_index([("location", "2dsphere")])
        await feed_snapshots.create_index("snapshot_time", expireAfterSeconds=7200)
        await llm_outputs.create_index([("incident_id", 1)])
        await chat_history.create_index([("incident_id", 1)])
        await signal_baselines.create_index([("city", 1), ("intersection_name", 1)])
        await diversion_routes.create_index([("city", 1), ("blocked_segment_id", 1)])
        await cctv_events.create_index([("city", 1), ("incident_id", 1)])
        await cctv_events.create_index([("camera_location", "2dsphere")])
        await cctv_events.create_index([("event_type", 1), ("detected_at", -1)])
        await congestion_zones.create_index([("city", 1), ("status", 1)])
        await congestion_zones.create_index([("location", "2dsphere")])
        await congestion_zones.create_index([("detected_at", -1)])
        await intersections.create_index([("city", 1), ("name", 1)])
        await road_segments.create_index([("city", 1), ("segment_id", 1)])

        logger.info(f"Connected to MongoDB: {settings.mongodb_db_name}")

    except Exception as e:
        logger.warning(f"MongoDB not available ({e}). Running in offline mode — DB writes will be skipped.")


async def close_db():
    global client
    if client:
        client.close()
        logger.info("MongoDB connection closed")


def get_db():
    return db
