-- Autonomous Notes table schema for Cars with a Life
-- Stores generated driving notes with validation results

CREATE TABLE IF NOT EXISTS `{project_id}.{dataset}.autonomous_notes` (
  note_id STRING NOT NULL OPTIONS(description="Unique identifier for the note"),
  experiment_id STRING NOT NULL OPTIONS(description="Reference to the experiment"),
  timestamp TIMESTAMP NOT NULL OPTIONS(description="When the note was generated"),
  location STRING NOT NULL OPTIONS(description="Location where the action occurred"),
  action STRING NOT NULL OPTIONS(description="Driving action taken"),
  destination STRING NOT NULL OPTIONS(description="Target destination or POI"),
  confidence FLOAT64 OPTIONS(description="AI confidence score for the decision"),
  validation_status STRING NOT NULL OPTIONS(description="Note validation result: valid, invalid, pending"),
  location_accuracy FLOAT64 OPTIONS(description="Accuracy score for location prediction"),
  action_accuracy FLOAT64 OPTIONS(description="Accuracy score for action prediction"),
  destination_accuracy FLOAT64 OPTIONS(description="Accuracy score for destination prediction"),
  map_reference STRING OPTIONS(description="Reference to map data used for validation"),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP() OPTIONS(description="Record creation timestamp")
)
PARTITION BY DATE(timestamp)
CLUSTER BY experiment_id, validation_status
OPTIONS(
  description="Generated autonomous driving notes with validation results",
  labels=[("system", "cars-with-a-life"), ("component", "notes")]
);