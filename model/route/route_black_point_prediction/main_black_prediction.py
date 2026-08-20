import asyncio
from accident_black_point_prediction_model import accident_black_main
from behavior_black_point_prediction_model import behavior_black_main

if __name__ == "__main__":
    asyncio.run(behavior_black_main())
    asyncio.run(accident_black_main())