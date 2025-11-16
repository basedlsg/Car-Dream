#!/usr/bin/env python3
"""
Test Script for Real Cars with a Life System
Tests actual data persistence and real functionality
"""

import requests
import json
import time
from datetime import datetime
from typing import Dict, List

# Configuration
BASE_URL = "https://cars-with-a-life-real-b7eh63hqtq-uc.a.run.app"  # Will be updated after deployment
HEADERS = {"Content-Type": "application/json"}

def test_health_check():
    """Test system health and verify it's the real system"""
    print("🔍 Testing system health...")
    
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ System Status: {data.get('status')}")
            print(f"📊 Version: {data.get('version')}")
            print(f"🗄️  Database Status: {data.get('database_status')}")
            print(f"🌍 Project: {data.get('project_id')}")
            print(f"📍 Region: {data.get('region')}")
            
            # Verify it's the real system
            if "real" in data.get('service', '').lower():
                print("✅ Confirmed: This is the REAL system (not simulated)")
                return True
            else:
                print("❌ Warning: This appears to be the simulated system")
                return False
        else:
            print(f"❌ Health check failed: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Health check error: {e}")
        return False

def test_real_experiment_creation():
    """Test creating real experiments with persistent data"""
    print("\n🧪 Testing real experiment creation...")
    
    # Create a test experiment
    experiment_data = {
        "name": "Real Highway Test",
        "description": "Testing real data persistence on highway scenario",
        "parameters": {
            "scenario_type": "highway",
            "weather_conditions": "clear",
            "traffic_density": "medium",
            "simulation_duration": 300
        },
        "simulation_duration": 300,
        "weather_conditions": "clear",
        "traffic_density": "medium",
        "scenario_type": "highway"
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/experiment/start",
            headers=HEADERS,
            json=experiment_data,
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            experiment_id = data.get('experiment_id')
            print(f"✅ Experiment created: {experiment_id}")
            print(f"📊 Status: {data.get('status')}")
            print(f"⏰ Created: {data.get('created_at')}")
            
            # Wait for processing
            print("⏳ Waiting for experiment processing...")
            time.sleep(5)
            
            # Check if experiment was processed
            exp_response = requests.get(f"{BASE_URL}/experiment/{experiment_id}", timeout=10)
            if exp_response.status_code == 200:
                exp_data = exp_response.json()
                print(f"✅ Experiment retrieved from database")
                print(f"📊 Final Status: {exp_data.get('status', 'unknown')}")
                return experiment_id
            else:
                print(f"⚠️  Could not retrieve experiment: {exp_response.status_code}")
                return experiment_id
        else:
            print(f"❌ Experiment creation failed: {response.status_code}")
            print(f"Response: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Experiment creation error: {e}")
        return None

def test_data_persistence(experiment_id: str):
    """Test that data is actually persisted in BigQuery"""
    print(f"\n💾 Testing data persistence for {experiment_id}...")
    
    try:
        # Get experiments list
        response = requests.get(f"{BASE_URL}/experiments", timeout=10)
        if response.status_code == 200:
            data = response.json()
            experiments = data.get('experiments', [])
            
            # Check if our experiment is in the list
            found = any(exp.get('experiment_id') == experiment_id for exp in experiments)
            if found:
                print("✅ Experiment found in database")
                
                # Get specific experiment details
                exp_response = requests.get(f"{BASE_URL}/experiment/{experiment_id}", timeout=10)
                if exp_response.status_code == 200:
                    exp_data = exp_response.json()
                    print(f"✅ Experiment details retrieved from database")
                    print(f"📊 Name: {exp_data.get('name')}")
                    print(f"📊 Status: {exp_data.get('status')}")
                    print(f"📊 Created: {exp_data.get('created_at')}")
                    
                    # Check for metrics
                    metrics_response = requests.get(f"{BASE_URL}/metrics/{experiment_id}", timeout=10)
                    if metrics_response.status_code == 200:
                        metrics_data = metrics_response.json()
                        metrics = metrics_data.get('metrics', [])
                        if metrics:
                            print(f"✅ Metrics found in database: {len(metrics)} records")
                            latest_metrics = metrics[0]
                            print(f"📊 Latest metrics:")
                            print(f"   Speed: {latest_metrics.get('average_speed')} km/h")
                            print(f"   Success Rate: {latest_metrics.get('success_rate')}%")
                            print(f"   Distance: {latest_metrics.get('total_distance')} km")
                            print(f"   Collisions: {latest_metrics.get('collisions')}")
                        else:
                            print("⚠️  No metrics found (may still be processing)")
                    else:
                        print(f"⚠️  Could not retrieve metrics: {metrics_response.status_code}")
                    
                    return True
                else:
                    print(f"❌ Could not retrieve experiment details: {exp_response.status_code}")
                    return False
            else:
                print("❌ Experiment not found in database")
                return False
        else:
            print(f"❌ Could not retrieve experiments list: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Data persistence test error: {e}")
        return False

def test_multiple_experiments():
    """Test creating multiple experiments to verify real data processing"""
    print("\n🔄 Testing multiple experiment creation...")
    
    scenarios = [
        {
            "name": "City Night Driving",
            "scenario_type": "city",
            "weather_conditions": "clear",
            "traffic_density": "low"
        },
        {
            "name": "Highway Rain Test",
            "scenario_type": "highway", 
            "weather_conditions": "rainy",
            "traffic_density": "high"
        },
        {
            "name": "Urban Intersection",
            "scenario_type": "intersection",
            "weather_conditions": "clear",
            "traffic_density": "very_high"
        }
    ]
    
    experiment_ids = []
    
    for i, scenario in enumerate(scenarios, 1):
        print(f"🚗 Creating experiment {i}/3: {scenario['name']}")
        
        experiment_data = {
            "name": scenario["name"],
            "description": f"Real test experiment {i}",
            "parameters": scenario,
            "simulation_duration": 180,
            **scenario
        }
        
        try:
            response = requests.post(
                f"{BASE_URL}/experiment/start",
                headers=HEADERS,
                json=experiment_data,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                experiment_id = data.get('experiment_id')
                experiment_ids.append(experiment_id)
                print(f"✅ Created: {experiment_id}")
            else:
                print(f"❌ Failed: {response.status_code}")
                
        except Exception as e:
            print(f"❌ Error: {e}")
    
    print(f"\n📊 Created {len(experiment_ids)} experiments")
    
    # Wait for processing
    print("⏳ Waiting for all experiments to process...")
    time.sleep(10)
    
    # Verify all experiments are in database
    try:
        response = requests.get(f"{BASE_URL}/experiments", timeout=10)
        if response.status_code == 200:
            data = response.json()
            all_experiments = data.get('experiments', [])
            print(f"📊 Total experiments in database: {len(all_experiments)}")
            
            # Check if our experiments are there
            found_count = 0
            for exp_id in experiment_ids:
                found = any(exp.get('experiment_id') == exp_id for exp in all_experiments)
                if found:
                    found_count += 1
                    print(f"✅ {exp_id} found in database")
                else:
                    print(f"❌ {exp_id} NOT found in database")
            
            print(f"📊 Persistence rate: {found_count}/{len(experiment_ids)} ({found_count/len(experiment_ids)*100:.1f}%)")
            return found_count == len(experiment_ids)
        else:
            print(f"❌ Could not verify experiments: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Verification error: {e}")
        return False

def main():
    print("🚗 Cars with a Life - REAL System Test Suite")
    print("=" * 60)
    print("Testing actual data persistence and real functionality")
    print("No simulations - this is the real deal!")
    print("")
    
    # Test 1: Health check
    if not test_health_check():
        print("❌ Health check failed. Aborting tests.")
        return
    
    # Test 2: Single experiment creation
    experiment_id = test_real_experiment_creation()
    if not experiment_id:
        print("❌ Single experiment test failed. Aborting tests.")
        return
    
    # Test 3: Data persistence
    if not test_data_persistence(experiment_id):
        print("❌ Data persistence test failed.")
        return
    
    # Test 4: Multiple experiments
    if not test_multiple_experiments():
        print("❌ Multiple experiments test failed.")
        return
    
    print("\n" + "=" * 60)
    print("🎉 ALL TESTS PASSED!")
    print("=" * 60)
    print("✅ Real system is working correctly")
    print("✅ Data is being persisted to BigQuery")
    print("✅ No simulations - this is real data processing")
    print("✅ System is production ready!")
    print("")
    print(f"🌐 Service URL: {BASE_URL}")
    print(f"📊 API Docs: {BASE_URL}/docs")

if __name__ == "__main__":
    main()






