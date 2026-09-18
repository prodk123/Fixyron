export interface RepositoryInfo {
  url: string;
  name: string | null;
  primary_language: string | null;
  framework: string | null;
  file_count: number;
  estimated_loc: number;
  has_readme: boolean;
}

export interface TestingInfo {
  framework: string | null;
  test_file_count: number;
}

export interface RepositoryStructure {
  important_directories: string[];
}

export interface RepositoryAnalysisResponse {
  analysis_id: string;
  repository: RepositoryInfo;
  testing: TestingInfo;
  structure: RepositoryStructure;
  relevant_files: string[];
  status: 'pending' | 'cloning' | 'analyzing' | 'completed' | 'failed';
  error_message: string | null;
  created_at: string;
  completed_at: string | null;
}

export interface TestRun {
  id: string;
  status: string;
  framework: string | null;
  command: string | null;
  tests_total: number;
  tests_passed: number;
  tests_failed: number;
  created_at: string;
  duration_ms: number | null;
  stdout?: string;
  stderr?: string;
}

export interface ReproductionAttempt {
  id: string;
  analysis_id: string;
  bug_description: string;
  test_framework: string | null;
  test_code: string | null;
  target_files: string[] | null;
  hypothesis: string | null;
  classification: 'pending' | 'reproduced' | 'not_reproduced' | 'inconclusive';
  evidence: any | null;
  confidence: number | null;
  created_at: string;
}

export interface EvidenceItem {
  type: string;
  file: string | null;
  line: number | null;
  description: string;
}

export interface AlternativeCause {
  description: string;
  confidence: number;
}

export interface CodeContext {
  file: string;
  start_line: number;
  end_line: number;
  content: string;
  score: number;
  reason: string;
}

export interface DiagnosisResult {
  id: string;
  analysis_id: string;
  reproduction_id: string;
  summary: string | null;
  root_cause: string | null;
  failure_mechanism: string | null;
  affected_files: string[] | null;
  affected_functions: string[] | null;
  evidence: EvidenceItem[] | null;
  alternative_causes: AlternativeCause[] | null;
  code_context: CodeContext[] | null;
  confidence: number | null;
  confidence_level: 'HIGH' | 'MEDIUM' | 'LOW' | null;
  status: 'pending' | 'collecting_context' | 'analyzing' | 'validating' | 'completed' | 'failed' | 'inconclusive';
  model: string | null;
  error_message: string | null;
  created_at: string;
  completed_at: string | null;
}

export interface FilePatch {
  path: string;
  operation: string;
  patch: string;
}

export interface RepairResult {
  id: string;
  analysis_id: string;
  reproduction_id: string;
  diagnosis_id: string;
  status: 'pending' | 'generating' | 'validating' | 'rejected' | 'applied' | 'tested' | 'failed' | 'error' | 'completed';
  summary: string | null;
  confidence: number | null;
  files_changed: number | null;
  lines_added: number | null;
  lines_removed: number | null;
  patch: string | null;
  patch_metadata: any | null;
  test_result: any | null;
  error_message: string | null;
  created_at: string;
  completed_at: string | null;
  max_attempts?: number;
  current_attempt?: number;
  final_status?: string;
  verification_status?: string;
}

export interface RepairAttemptData {
  id: string;
  attempt_number: number;
  strategy: any | null;
  patch_metadata: any | null;
  validation_result: any | null;
  reproduction_result: any | null;
  regression_result: any | null;
  review: any | null;
  failure_category: string | null;
  status: string;
  error_message: string | null;
  created_at: string;
  completed_at: string | null;
}

export interface PublicationData {
  id: string;
  repair_id: string;
  status: string;
  pull_request_url: string | null;
  pull_request_number: number | null;
  pull_request_state: string | null;
  branch_name: string | null;
  commit_sha: string | null;
  error_message: string | null;
  created_at: string;
  completed_at: string | null;
}
