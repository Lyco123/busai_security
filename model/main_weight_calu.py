import asyncio

from model.driver.driver_accident_calculate_scores import driver_accident_weights
from model.driver.driver_accident_train_weights import accident_weights_main
from model.driver.driver_attitude_score import driver_attitude_weight_main
from model.driver.driver_calculate_safety_scores import driver_safety_weight_main
from model.driver.main import driver_energy_weights
from model.route.main_route_quota_weight_month import route_quota_weight_main
from model.vehicle.app_weight_update import vehicle_weight_main

if __name__ == "__main__":
    #计算驾驶员能耗风险权重
    # asyncio.run(driver_energy_weights())
    #计算驾驶员事故风险权重
    # asyncio.run(accident_weights_main())
    # asyncio.run(driver_accident_weights())

    #计算驾驶员安全评价风险权重
    # asyncio.run(driver_safety_weight_main())

    # 计算驾驶员服务态度风险权重
    # asyncio.run(driver_attitude_weight_main())

    #计算线路风险权重
    asyncio.run(route_quota_weight_main())


    #计算车辆风险权重
    # asyncio.run(vehicle_weight_main())

    import gc
    gc.collect()

