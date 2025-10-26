-- Experiments table schema for Cars with a Life
-- Stores metadata and results for each autonomous driving experiment

CREATE TABLE IF NOT EXISTS `{project_id}.{dataset}.experiments` (
  experiment_id STRING NOT NULL OPTIONS(description="Unique identifier for the experiment"),
  start_time TIMESTAMP NOT NULL OPTIONS(description="When the experiment started"),
  end_time TIMESTAMP OPTIONS(description="When the experiment completed"),
  scenario_name STRING NOT NULL OPTIONS(description="Name of the driving scenario"),
  map_name STRING NOT NULL OPTIONS(description="CARLA map used for the experiment"),
  status STRING NOT NULL OPTIONS(description="Experiment status: running, completed, failed"),
  ai_model_version STRING NOT NULL OPTIONS(description="Version of the AI model used"),
  total_notes INTEGER OPTIONS(description="Total number of autonomous notes generated"),
  overall_score FLOAT64 OPTIONS(description="Overall experiment performance score"),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP() OPTIONS(description="Record creation timestamp"),
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP() OPTIONS(description="Record last update timestamp")
)
PARTITION BY DATE(start_time)
CLUSTER BY status, scenario_name
OPTIONS(
  description="Experiment metadata and results for autonomous driving experiments",
  labels=[("system", "cars-with-a-life"), ("component", "experiments")]
);