-- Evaluation Metrics table schema for Cars with a Life
-- Stores performance metrics and evaluation data

CREATE TABLE IF NOT EXISTS `{project_id}.{dataset}.evaluation_metrics` (
  experiment_id STRING NOT NULL OPTIONS(description="Reference to the experiment"),
  metric_name STRING NOT NULL OPTIONS(description="Name of the performance metric"),
  metric_value FLOAT64 NOT NULL OPTIONS(description="Numerical value of the metric"),
  calculation_time TIMESTAMP NOT NULL OPTIONS(description="When the metric was calculated"),
  metadata JSON OPTIONS(description="Additional metadata about the metric calculation"),
  metric_category STRING OPTIONS(description="Category of metric: accuracy, performance, safety"),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP() OPTIONS(description="Record creation timestamp")
)
PARTITION BY DATE(calculation_time)
CLUSTER BY experiment_id, metric_name
OPTIONS(
  description="Evaluation metrics and performance data for autonomous driving experiments",
  labels=[("system", "cars-with-a-life"), ("component", "metrics")]
);