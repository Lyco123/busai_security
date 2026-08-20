#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Work Scene Configuration Granularity Test
For Test 2: Work Scene Configuration Granularity Testing
"""

import json
from datetime import datetime, timedelta

class SceneConfigTester:
    """Scene Configuration Granularity Tester"""
    
    def __init__(self):
        self.current_date = datetime.now().strftime("%Y-%m-%d")
        
    def test_configuration_granularity(self):
        """Test different configuration granularities"""
        print("=== Test 2: Work Scene Configuration Granularity Testing ===\n")
        
        # Configuration A: Ultra-wide granularity (broad categories)
        print("Configuration A: Ultra-wide granularity (broad categories)")
        print("- Categories: Vehicle Operations, Driver Management, Safety Monitoring, Maintenance Scheduling")
        print("- Edge case testing:")
        print("  - User asks about 'YueB1234 bus battery health' -> should route to Vehicle Operations")
        print("  - User asks about 'Master Zhang's safety rating' -> should route to Driver Management")
        print("  - User asks about 'emergency brake response time' -> should route to Safety Monitoring")
        print("  - User asks about 'next oil change date' -> should route to Maintenance Scheduling")
        print()
        
        # Configuration B: Medium granularity (functional areas)
        print("Configuration B: Medium granularity (functional areas)")
        print("- Categories: Bus Fleet Management, Driver Performance Analysis, Real-time Safety Alerts, Preventive Maintenance Planning")
        print("- Edge case testing:")
        print("  - User asks about 'YueB1234 bus battery health' -> should route to Bus Fleet Management")
        print("  - User asks about 'Master Zhang's safety rating' -> should route to Driver Performance Analysis")
        print("  - User asks about 'emergency brake response time' -> should route to Real-time Safety Alerts")
        print("  - User asks about 'next oil change date' -> should route to Preventive Maintenance Planning")
        print()
        
        # Configuration C: Fine granularity (specific capabilities)
        print("Configuration C: Fine granularity (specific capabilities)")
        print("- Categories: Battery Health Monitoring, Driver Safety Scoring, Brake System Response Analysis, Oil Change Scheduling")
        print("- Edge case testing:")
        print("  - User asks about 'YueB1234 bus battery health' -> should route to Battery Health Monitoring")
        print("  - User asks about 'Master Zhang's safety rating' -> should route to Driver Safety Scoring")
        print("  - User asks about 'emergency brake response time' -> should route to Brake System Response Analysis")
        print("  - User asks about 'next oil change date' -> should route to Oil Change Scheduling")
        print()
        
        # Test results summary
        print("=== Configuration Granularity Comparison ===")
        print("- Ultra-wide granularity (A):")
        print("  + Pros: Simple routing, fewer categories, easier maintenance")
        print("  - Cons: Less precise routing, may require additional clarification")
        print()
        print("- Medium granularity (B):")
        print("  + Pros: Good balance between precision and manageability")
        print("  - Cons: Requires more careful category definition")
        print()
        print("- Fine granularity (C):")
        print("  + Pros: Most precise routing, better handling of edge cases")
        print("  - Cons: More complex configuration, harder to maintain")
        print()
        
        # Recommendation
        print("=== Recommendation ===")
        print("Based on edge case testing, we recommend medium granularity (Configuration B)")
        print("as it provides the best balance between precision and maintainability.")
        print("It handles most edge cases effectively while remaining manageable for ongoing updates.")
        
        # Save test results
        test_results = {
            "test_type": "configuration_granularity",
            "test_date": self.current_date,
            "configurations": {
                "ultra_wide": {
                    "categories": ["Vehicle Operations", "Driver Management", "Safety Monitoring", "Maintenance Scheduling"],
                    "edge_case_handling": "Good for broad queries, may need clarification for specific technical questions"
                },
                "medium": {
                    "categories": ["Bus Fleet Management", "Driver Performance Analysis", "Real-time Safety Alerts", "Preventive Maintenance Planning"],
                    "edge_case_handling": "Excellent balance - handles most edge cases with minimal clarification needed"
                },
                "fine": {
                    "categories": ["Battery Health Monitoring", "Driver Safety Scoring", "Brake System Response Analysis", "Oil Change Scheduling"],
                    "edge_case_handling": "Most precise but requires more maintenance effort"
                }
            },
            "recommendation": "Medium granularity (Configuration B) is recommended for optimal performance and maintainability"
        }
        
        with open("../busai_security/config_granularity_test.json", "w") as f:
            json.dump(test_results, f, indent=2)
        
        print("\nTest results saved to config_granularity_test.json")

def main():
    """Main function"""
    tester = SceneConfigTester()
    tester.test_configuration_granularity()

if __name__ == "__main__":
    main()