export interface User {
  id: string;
  name: string;
  created_at: string;
  avatar_color: string;
  preferences: string;
  has_profile: boolean;
  learning_phase: number;
  confidence: Record<string, number>;
}

export interface BrainData {
  type: "brain_data";
  signal_quality: number;
  bands: Record<string, number>;
  horseshoe: number[];
  trend: Record<string, number[]>;
  accelerometer: Record<string, number>;
  snapshot_number: number;
  session_duration: number;
  touching_forehead: boolean;
}

export interface SessionStatus {
  id: string;
  user_id: string;
  active: boolean;
  source: string;
  snapshot_count: number;
  generation_count: number;
  signal_quality: number;
}

export interface ExperimentTask {
  id: string;
  experiment_id: string;
  task_order: number;
  task_type: string;
  instruction: string;
  duration_seconds: number;
  interpretation: string;
  started_at: string | null;
  completed_at: string | null;
}

export interface Experiment {
  id: string;
  user_id: string;
  phase: number;
  status: string;
  started_at: string | null;
  completed_at: string | null;
  current_task: ExperimentTask | null;
  total_tasks: number;
  completed_tasks: number;
}

export interface NeuralProfile {
  user_id: string;
  learning_phase: number;
  domain_baselines: Record<string, Record<string, { mean: number; std: number }>>;
  claude_observations: Array<{ task_type: string; observation: string; timestamp: string }>;
  discrimination_summary: string;
  confidence: Record<string, number>;
}

export interface Output {
  id: string;
  user_id: string;
  file_path: string;
  file_type: string;
  detected_mode: string;
  neuron_header: string;
  neural_summary: string;
  created_at: string;
}

export type WSMessage =
  | BrainData
  | { type: "experiment_started"; experiment_id: string; total_tasks: number; first_task: ExperimentTask | null }
  | { type: "experiment_instruction"; task_id: string; task_type: string; instruction: string; duration_seconds: number }
  | { type: "experiment_interpretation"; task_id: string; task_type: string; interpretation: string }
  | { type: "experiment_complete"; experiment_id: string; discrimination_summary: string; confidence: Record<string, number>; learning_phase: number }
  | { type: "generation_started"; mode: string }
  | { type: "generation_chunk"; text: string }
  | { type: "generation_complete"; output: Output }
  | { type: "error"; message: string }
  | { type: "pong" };
