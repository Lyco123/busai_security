#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Simple Vehicle and Driver Report Generator
For Test 1: Vehicle Report and Driver Report Generation and Follow-up Questions
"""

import json
from datetime import datetime, timedelta

class ReportGenerator:
    """Simple Report Generator Class"""
    
    def __init__(self):
        self.current_date = datetime.now().strftime("%Y-%m-%d")
        
    def generate_vehicle_report(self, plate_number="YueB1234"):
        """Generate vehicle report"""
        return {
            "report_type": "vehicle",
            "report_date": self.current_date,
            "plate_number": plate_number,
            "total_mileage": 128.5,
            "energy_consumption": 185.2,
            "fault_records": [
                {"type": "Air Conditioning System Abnormal", "status": "Processed"},
                {"type": "Door Sensor Fault", "status": "Pending"}
            ],
            "summary": plate_number + " bus operated normally today with 128.5 km mileage and 185.2 kWh energy consumption."
        }
    
    def generate_driver_report(self, driver_name="Master Zhang"):
        """Generate driver report"""
        return {
            "report_type": "driver",
            "report_date": self.current_date,
            "driver_name": driver_name,
            "working_hours": 12.5,
            "safety_rating": 92.5,
            "violation_records": 1,
            "summary": driver_name + " performed excellently today with 12.5 working hours and 92.5 safety rating."
        }

def main():
    """Main function"""
    generator = ReportGenerator()
    
    print("=== Test 1: Vehicle Report and Driver Report Generation ===\n")
    
    # Round 1: Vehicle report
    print("Round 1: Vehicle Report Generation")
    print("User: Please generate today's operation report for YueB1234 bus")
    vehicle_report = generator.generate_vehicle_report("YueB1234")
    print("\nAI Response:")
    print("- License Plate: " + vehicle_report['plate_number'])
    print("- Total Mileage: " + str(vehicle_report['total_mileage']) + " km")
    print("- Energy Consumption: " + str(vehicle_report['energy_consumption']) + " kWh")
    print("- Summary: " + vehicle_report['summary'])
    print()
    
    # Round 2: Vehicle follow-up
    print("Round 2: Vehicle Report Follow-up")
    print("User: How much higher is this bus's energy consumption compared to the average?")
    print("\nAI Response:")
    print("- Energy consumption is 185.2 kWh, which is 9.4 kWh higher than the average of 175.8 kWh.")
    print()
    
    # Round 3: Driver report
    print("Round 3: Driver Report Generation")
    print("User: Please generate Master Zhang's work report for today")
    driver_report = generator.generate_driver_report("Master Zhang")
    print("\nAI Response:")
    print("- Driver Name: " + driver_report['driver_name'])
    print("- Working Hours: " + str(driver_report['working_hours']) + " hours")
    print("- Safety Rating: " + str(driver_report['safety_rating']) + " points")
    print("- Summary: " + driver_report['summary'])
    print()
    
    # Round 4: Driver follow-up
    print("Round 4: Driver Report Follow-up")
    print("User: How are Master Zhang's accident and violation records this month?")
    print("\nAI Response:")
    print("- This month: 1 violation record, no accidents.")
    print("- Safety rating: 92.5 points (above team average).")
    
    # Save reports
    with open("../busai_security/vehicle_report.json", "w") as f:
        json.dump(vehicle_report, f, indent=2)
    
    with open("../busai_security/driver_report.json", "w") as f:
        json.dump(driver_report, f, indent=2)
    
    print("\nReports saved to:")
    print("- vehicle_report.json")
    print("- driver_report.json")

if __name__ == "__main__":
    main()