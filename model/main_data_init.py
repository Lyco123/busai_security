import asyncio

from model.driver.main import driver_behavior_data_init, driver_weight_data_init

if __name__ == "__main__":
    asyncio.run(driver_behavior_data_init())
    # asyncio.run(driver_weight_data_init())


