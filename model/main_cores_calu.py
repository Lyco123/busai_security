import asyncio

from model.driver.driver_accident_calculate_scores import driver_accident_cores
from model.driver.driver_attitude_score import driver_attitude_scores_main
from model.driver.driver_calculate_safety_scores import driver_safety_cores_main
# from model.driver.main import driver_energy_cores, driver_scores_main
from model.route.main_route_risk_score import route_cores
from model.route.route_black_point_prediction.accident_black_point_prediction_model import accident_black_main
from model.route.route_black_point_prediction.behavior_black_point_prediction_model import behavior_black_main
from model.vehicle.app_score_update import vehicle_score_main

# from model.vehicle.main import vechicle_score_main

if __name__ == "__main__":
    #计算驾驶员能耗风险分数(一周一次，改成按天计算)
    # asyncio.run(driver_energy_cores())

    #计算驾驶员事故风险(一天一次)
    # asyncio.run(driver_accident_cores())

    #计算驾驶员安全评价分数
    # asyncio.run(driver_safety_cores_main())

    #计算驾驶员服务态度分数
    # asyncio.run(driver_attitude_scores_main())

    #计算驾驶员总分
    # asyncio.run(driver_scores_main())


    #计算线路分数(一周一次)
    # asyncio.run(route_cores())
    # 计算车辆分数(一周一次)
    # asyncio.run(vehicle_score_main())


    #计算行为黑点（一周一次）
    asyncio.run(behavior_black_main())
    #计算事故黑点
    # asyncio.run(accident_black_main())
    import gc
    gc.collect()

