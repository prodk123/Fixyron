import { RepositoryAnalysisResponse } from '../types/repository';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';

export async function analyzeRepository(url: string, bugDescription?: string): Promise<RepositoryAnalysisResponse> {
  const response = await fetch(`${API_BASE_URL}/repositories/analyze`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      repository_url: url,
      bug_description: bugDescription || undefined,
    }),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => null);
    throw new Error(errorData?.detail || 'Failed to start analysis');
  }

  return response.json();
}

export async function getRepositoryAnalysis(id: string): Promise<RepositoryAnalysisResponse> {
  const response = await fetch(`${API_BASE_URL}/repositories/${id}`);

  if (!response.ok) {
    const errorData = await response.json().catch(() => null);
    throw new Error(errorData?.detail || 'Failed to fetch analysis');
  }

  return response.json();
}

export async function checkHealth(): Promise<{ status: string; service: string }> {
  const response = await fetch(`${API_BASE_URL}/health`);
  return response.json();
}

export async function runExistingTests(analysisId: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/qa/tests/run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ analysis_id: analysisId }),
  });
  if (!response.ok) throw new Error('Failed to start tests');
}

export async function getTestRuns(analysisId: string): Promise<any[]> {
  const response = await fetch(`${API_BASE_URL}/qa/tests/analysis/${analysisId}`);
  if (!response.ok) throw new Error('Failed to fetch test runs');
  return response.json();
}

export async function getTestRun(runId: string): Promise<any> {
  const response = await fetch(`${API_BASE_URL}/qa/tests/${runId}`);
  if (!response.ok) throw new Error('Failed to fetch test run');
  return response.json();
}

export async function triggerReproduction(analysisId: string, bugDescription: string): Promise<any> {
  const response = await fetch(`${API_BASE_URL}/qa/reproduction`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ analysis_id: analysisId, bug_description: bugDescription }),
  });
  if (!response.ok) throw new Error('Failed to start reproduction');
  return response.json();
}

export async function getReproductions(analysisId: string): Promise<any[]> {
  const response = await fetch(`${API_BASE_URL}/qa/reproduction/analysis/${analysisId}`);
  if (!response.ok) throw new Error('Failed to fetch reproductions');
  return response.json();
}

export async function triggerDiagnosis(analysisId: string, reproductionId: string): Promise<any> {
  const response = await fetch(`${API_BASE_URL}/diagnosis/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ analysis_id: analysisId, reproduction_id: reproductionId }),
  });
  if (!response.ok) throw new Error('Failed to start diagnosis');
  return response.json();
}

export async function getDiagnosis(diagnosisId: string): Promise<any> {
  const response = await fetch(`${API_BASE_URL}/diagnosis/${diagnosisId}`);
  if (!response.ok) throw new Error('Failed to fetch diagnosis');
  return response.json();
}

export async function getDiagnosesForAnalysis(analysisId: string): Promise<any[]> {
  const response = await fetch(`${API_BASE_URL}/diagnosis/analysis/${analysisId}`);
  if (!response.ok) throw new Error('Failed to fetch diagnoses');
  return response.json();
}

export async function triggerRepair(analysisId: string, reproductionId: string, diagnosisId: string): Promise<any> {
  const response = await fetch(`${API_BASE_URL}/repair/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      analysis_id: analysisId,
      reproduction_id: reproductionId,
      diagnosis_id: diagnosisId,
    }),
  });
  if (!response.ok) throw new Error('Failed to start repair');
  return response.json();
}

export async function getRepair(repairId: string): Promise<any> {
  const response = await fetch(`${API_BASE_URL}/repair/${repairId}`);
  if (!response.ok) throw new Error('Failed to fetch repair');
  return response.json();
}

export async function getRepairsForAnalysis(analysisId: string): Promise<any[]> {
  const response = await fetch(`${API_BASE_URL}/repair/analysis/${analysisId}`);
  if (!response.ok) throw new Error('Failed to fetch repairs');
  return response.json();
}

export async function verifyRepair(repairId: string): Promise<any> {
  const response = await fetch(`${API_BASE_URL}/repair/${repairId}/verify`, {
    method: 'POST',
  });
  if (!response.ok) throw new Error('Failed to verify repair');
  return response.json();
}

export async function getRepairAttempts(repairId: string): Promise<any[]> {
  const response = await fetch(`${API_BASE_URL}/repair/${repairId}/attempts`);
  if (!response.ok) throw new Error('Failed to fetch repair attempts');
  return response.json();
}

export async function publishRepair(repairId: string): Promise<any> {
  const response = await fetch(`${API_BASE_URL}/repair/${repairId}/publish`, {
    method: 'POST',
  });
  if (!response.ok) {
    const errorData = await response.json().catch(() => null);
    throw new Error(errorData?.detail || 'Failed to publish repair');
  }
  return response.json();
}

export async function getPublication(repairId: string): Promise<any> {
  const response = await fetch(`${API_BASE_URL}/repair/${repairId}/publication`);
  if (!response.ok) {
    if (response.status === 404) return null;
    throw new Error('Failed to fetch publication');
  }
  return response.json();
}
