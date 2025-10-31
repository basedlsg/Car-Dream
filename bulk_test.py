#!/usr/bin/env python3
"""
Bulk Test Script for Cars with a Life
Generates loads of test data with various scenarios
"""

import requests
import json
import time
import random
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# Configuration
BASE_URL = "https://cars-with-a-life-b7eh63hqtq-uc.a.run.app"
HEADERS = {"Content-Type": "application/json"}

# Test scenarios
SCENARIOS = [
    {
        "name": "Highway Rush Hour",
        "description": "Highway driving during peak traffic",
        "parameters": {
            "simulation_duration": 600,
            "weather_conditions": "clear",
            "traffic_density": "high",
            "scenario": "highway_rush_hour",
            "time_of_day": "morning"
        }
    },
    {
        "name": "City Night Driving",
        "description": "Urban driving at night with reduced visibility",
        "parameters": {
            "simulation_duration": 300,
            "weather_conditions": "clear",
            "traffic_density": "low",
            "scenario": "city_night",
            "time_of_day": "night"
        }
    },
    {
        "name": "Rainy Weather Test",
        "description": "Driving in heavy rain conditions",
        "parameters": {
            "simulation_duration": 400,
            "weather_conditions": "rainy",
            "traffic_density": "medium",
            "scenario": "rainy_weather",
            "visibility": "reduced"
        }
    },
    {
        "name": "Foggy Conditions",
        "description": "Driving in dense fog",
        "parameters": {
            "simulation_duration": 250,
            "weather_conditions": "foggy",
            "traffic_density": "low",
            "scenario": "foggy_conditions",
            "visibility": "very_low"
        }
    },
    {
        "name": "Construction Zone",
        "description": "Navigating through construction areas",
        "parameters": {
            "simulation_duration": 350,
            "weather_conditions": "clear",
            "traffic_density": "medium",
            "scenario": "construction_zone",
            "obstacles": "construction_barriers"
        }
    },
    {
        "name": "School Zone",
        "description": "Driving near schools with pedestrian traffic",
        "parameters": {
            "simulation_duration": 200,
            "weather_conditions": "clear",
            "traffic_density": "high",
            "scenario": "school_zone",
            "pedestrian_density": "high"
        }
    },
    {
        "name": "Mountain Pass",
        "description": "Driving through mountainous terrain",
        "parameters": {
            "simulation_duration": 500,
            "weather_conditions": "clear",
            "traffic_density": "low",
            "scenario": "mountain_pass",
            "elevation_change": "high"
        }
    },
    {
        "name": "Highway Merge",
        "description": "Complex highway merging scenarios",
        "parameters": {
            "simulation_duration": 180,
            "weather_conditions": "clear",
            "traffic_density": "high",
            "scenario": "highway_merge",
            "lane_changes": "frequent"
        }
    },
    {
        "name": "Urban Intersection",
        "description": "Complex urban intersection navigation",
        "parameters": {
            "simulation_duration": 220,
            "weather_conditions": "clear",
            "traffic_density": "very_high",
            "scenario": "urban_intersection",
            "traffic_lights": "multiple"
        }
    },
    {
        "name": "Parking Lot",
        "description": "Autonomous parking and maneuvering",
        "parameters": {
            "simulation_duration": 150,
            "weather_conditions": "clear",
            "traffic_density": "medium",
            "scenario": "parking_lot",
            "parking_spaces": "tight"
        }
    }
]

def run_experiment(scenario, experiment_id):
    """Run a single experiment"""
    try:
        print(f"🚗 Starting experiment {experiment_id}: {scenario['name']}")
        
        # Start experiment
        response = requests.post(
            f"{BASE_URL}/experiment/start",
            headers=HEADERS,
            json=scenario,
            timeout=30
        )
        
        if response.status_code == 201:
            data = response.json()
            experiment_id = data.get('experiment_id')
            print(f"✅ Experiment {experiment_id} completed successfully")
            
            # Get detailed results
            results = {
                'experiment_id': experiment_id,
                'scenario': scenario['name'],
                'status': data.get('status'),
                'metrics': data.get('metrics', {}),
                'created_at': data.get('created_at'),
                'timestamp': datetime.utcnow().isoformat()
            }
            
            # Get report
            try:
                report_response = requests.get(f"{BASE_URL}/reports/{experiment_id}", timeout=10)
                if report_response.status_code == 200:
                    report_data = report_response.json()
                    results['report'] = {
                        'summary': report_data.get('summary', {}),
                        'ai_insights': report_data.get('ai_insights', []),
                        'recommendations': report_data.get('recommendations', [])
                    }
            except Exception as e:
                print(f"⚠️  Could not fetch report for {experiment_id}: {e}")
            
            return results
        else:
            print(f"❌ Experiment {experiment_id} failed: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"❌ Error running experiment {experiment_id}: {e}")
        return None

def run_bulk_tests(num_experiments=50, max_workers=5):
    """Run bulk experiments with concurrent execution"""
    print(f"🚀 Starting bulk test with {num_experiments} experiments")
    print(f"📊 Using {max_workers} concurrent workers")
    print(f"🎯 Testing {len(SCENARIOS)} different scenarios")
    print("=" * 60)
    
    results = []
    start_time = time.time()
    
    # Create experiment list with random scenario selection
    experiments = []
    for i in range(num_experiments):
        scenario = random.choice(SCENARIOS).copy()
        scenario['name'] = f"{scenario['name']} #{i+1:03d}"
        experiments.append((scenario, i+1))
    
    # Run experiments concurrently
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all experiments
        future_to_exp = {
            executor.submit(run_experiment, scenario, exp_id): (scenario, exp_id)
            for scenario, exp_id in experiments
        }
        
        # Collect results as they complete
        for future in as_completed(future_to_exp):
            scenario, exp_id = future_to_exp[future]
            try:
                result = future.result()
                if result:
                    results.append(result)
                    print(f"📈 Progress: {len(results)}/{num_experiments} completed")
            except Exception as e:
                print(f"❌ Experiment {exp_id} failed: {e}")
    
    end_time = time.time()
    duration = end_time - start_time
    
    # Generate summary
    print("\n" + "=" * 60)
    print("🎉 BULK TEST COMPLETED!")
    print("=" * 60)
    print(f"⏱️  Total Duration: {duration:.2f} seconds")
    print(f"✅ Successful Experiments: {len(results)}")
    print(f"❌ Failed Experiments: {num_experiments - len(results)}")
    print(f"📊 Success Rate: {len(results)/num_experiments*100:.1f}%")
    print(f"🚀 Average Speed: {num_experiments/duration:.2f} experiments/second")
    
    # Scenario breakdown
    scenario_counts = {}
    for result in results:
        scenario = result['scenario'].split(' #')[0]
        scenario_counts[scenario] = scenario_counts.get(scenario, 0) + 1
    
    print(f"\n📋 Scenario Breakdown:")
    for scenario, count in scenario_counts.items():
        print(f"   {scenario}: {count} experiments")
    
    # Metrics summary
    if results:
        total_distance = sum(r['metrics'].get('total_distance', 0) for r in results)
        avg_speed = sum(r['metrics'].get('average_speed', 0) for r in results) / len(results)
        total_collisions = sum(r['metrics'].get('collisions', 0) for r in results)
        avg_success_rate = sum(r['metrics'].get('success_rate', 0) for r in results) / len(results)
        
        print(f"\n📊 Performance Summary:")
        print(f"   Total Distance Simulated: {total_distance:.1f} km")
        print(f"   Average Speed: {avg_speed:.1f} km/h")
        print(f"   Total Collisions: {total_collisions}")
        print(f"   Average Success Rate: {avg_success_rate:.1f}%")
    
    return results

def test_system_health():
    """Test system health and performance"""
    print("🔍 Testing system health...")
    
    try:
        # Health check
        health_response = requests.get(f"{BASE_URL}/health", timeout=10)
        if health_response.status_code == 200:
            health_data = health_response.json()
            print(f"✅ System Health: {health_data.get('status')}")
            print(f"📊 Version: {health_data.get('version')}")
            print(f"🌍 Region: {health_data.get('region')}")
        else:
            print(f"❌ Health check failed: {health_response.status_code}")
            return False
        
        # Test current experiments
        experiments_response = requests.get(f"{BASE_URL}/experiments", timeout=10)
        if experiments_response.status_code == 200:
            experiments_data = experiments_response.json()
            print(f"📈 Current Experiments: {experiments_data.get('count', 0)}")
        
        # Test reports
        reports_response = requests.get(f"{BASE_URL}/reports", timeout=10)
        if reports_response.status_code == 200:
            reports_data = reports_response.json()
            print(f"📋 Current Reports: {reports_data.get('count', 0)}")
        
        return True
        
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        return False

if __name__ == "__main__":
    print("🚗 Cars with a Life - Bulk Test Suite")
    print("=" * 60)
    
    # Test system health first
    if not test_system_health():
        print("❌ System health check failed. Aborting bulk test.")
        exit(1)
    
    print("\n🚀 Starting bulk experiment generation...")
    
    # Run bulk tests
    # You can adjust these parameters:
    # - num_experiments: Total number of experiments to run
    # - max_workers: Number of concurrent workers (be careful not to overload the system)
    results = run_bulk_tests(num_experiments=100, max_workers=10)
    
    print(f"\n🎉 Generated {len(results)} experiments with comprehensive data!")
    print("📊 Check the system dashboard for detailed analytics.")



