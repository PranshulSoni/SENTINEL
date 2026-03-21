import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

async def main():
    uri = "mongodb+srv://pranshulsoni2006marvel_db_user:vdTSdb1rrmPVFdSI@sentinel.worgkrj.mongodb.net/?appName=SENTINEL"
    client = AsyncIOMotorClient(uri)
    db = client.traffic_copilot
    
    # Find NYC incidents with Chandigarh streets and delete them
    res = await db.incidents.delete_many({
        "city": "nyc",
        "$or": [
            {"on_street": {"$regex": "Madhya", "$options": "i"}},
            {"on_street": {"$regex": "Sector", "$options": "i"}},
            {"on_street": {"$regex": "Marg", "$options": "i"}},
            {"on_street": {"$regex": "Chowk", "$options": "i"}}
        ]
    })
    print(f"Deleted {res.deleted_count} mismatched NYC incidents")
    
    # Also delete Chandigarh incidents with NYC streets
    res2 = await db.incidents.delete_many({
        "city": "chandigarh",
        "$or": [
            {"on_street": {"$regex": "Ave", "$options": "i"}},
            {"on_street": {"$regex": "St", "$options": "i"}},
            {"on_street": {"$regex": "Broadway", "$options": "i"}}
        ]
    })
    print(f"Deleted {res2.deleted_count} mismatched Chandigarh incidents")
    
    client.close()

asyncio.run(main())
