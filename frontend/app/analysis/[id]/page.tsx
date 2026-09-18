'use client';

import { useEffect, useState } from 'react';
import { getRepositoryAnalysis, runExistingTests, getTestRuns, triggerReproduction, getReproductions, triggerDiagnosis, getDiagnosesForAnalysis, triggerRepair, getRepairsForAnalysis, verifyRepair, getRepairAttempts, publishRepair, getPublication } from '../../../lib/api';
import { RepositoryAnalysisResponse, TestRun, ReproductionAttempt, DiagnosisResult, RepairResult, RepairAttemptData, PublicationData } from '../../../types/repository';
import { useParams, useRouter } from 'next/navigation';

export default function AnalysisPage() {
  const { id } = useParams();
  const router = useRouter();
  const [analysis, setAnalysis] = useState<RepositoryAnalysisResponse | null>(null);
  const [error, setError] = useState('');
  
  // QA state
  const [testRuns, setTestRuns] = useState<TestRun[]>([]);
  const [reproductions, setReproductions] = useState<ReproductionAttempt[]>([]);
  const [diagnoses, setDiagnoses] = useState<DiagnosisResult[]>([]);
  const [repairs, setRepairs] = useState<RepairResult[]>([]);
  const [repairAttemptsMap, setRepairAttemptsMap] = useState<Record<string, RepairAttemptData[]>>({});
  const [publicationsMap, setPublicationsMap] = useState<Record<string, PublicationData | null>>({});
  const [bugDescription, setBugDescription] = useState('');
  const [isTriggeringTest, setIsTriggeringTest] = useState(false);
  const [isTriggeringRepro, setIsTriggeringRepro] = useState(false);
  const [isTriggeringDiag, setIsTriggeringDiag] = useState(false);
  const [isTriggeringRepair, setIsTriggeringRepair] = useState(false);
  const [publishingRepair, setPublishingRepair] = useState<RepairResult | null>(null);
  const [expandedCode, setExpandedCode] = useState<string | null>(null);
  const [expandedTestRuns, setExpandedTestRuns] = useState<Set<string>>(new Set());
  const [expandedReproOutputs, setExpandedReproOutputs] = useState<Set<string>>(new Set());

  const toggleTestRun = (runId: string) => {
    setExpandedTestRuns(prev => {
      const next = new Set(prev);
      if (next.has(runId)) next.delete(runId);
      else next.add(runId);
      return next;
    });
  };

  const toggleReproOutput = (reproId: string) => {
    setExpandedReproOutputs(prev => {
      const next = new Set(prev);
      if (next.has(reproId)) next.delete(reproId);
      else next.add(reproId);
      return next;
    });
  };

  useEffect(() => {
    let interval: NodeJS.Timeout;

    const fetchStatus = async () => {
      try {
        const data = await getRepositoryAnalysis(id as string);
        setAnalysis(data);

        if (data.status === 'completed') {
          const runs = await getTestRuns(id as string);
          setTestRuns(runs);
          
          const repros = await getReproductions(id as string);
          setReproductions(repros);

          const diags = await getDiagnosesForAnalysis(id as string);
          setDiagnoses(diags);

          const reps = await getRepairsForAnalysis(id as string);
          setRepairs(reps);
          
          // Fetch attempts and publications for all repairs
          const attemptsMap: Record<string, RepairAttemptData[]> = {};
          const pubsMap: Record<string, PublicationData | null> = {};
          
          for (const rep of reps) {
            const attempts = await getRepairAttempts(rep.id);
            attemptsMap[rep.id] = attempts;
            
            const pub = await getPublication(rep.id);
            pubsMap[rep.id] = pub;
          }
          setRepairAttemptsMap(attemptsMap);
          setPublicationsMap(pubsMap);
        }
      } catch (err: any) {
        setError(err.message || 'Failed to fetch analysis status');
        clearInterval(interval);
      }
    };

    fetchStatus();
    interval = setInterval(fetchStatus, 3000);

    return () => clearInterval(interval);
  }, [id]);

  const handleRunTests = async () => {
    try {
      setIsTriggeringTest(true);
      await runExistingTests(id as string);
    } catch (err: any) {
      alert(err.message || 'Failed to run tests');
    } finally {
      setIsTriggeringTest(false);
    }
  };

  const handleReproduceBug = async () => {
    if (!bugDescription) return;
    try {
      setIsTriggeringRepro(true);
      await triggerReproduction(id as string, bugDescription);
      setBugDescription('');
    } catch (err: any) {
      alert(err.message || 'Failed to reproduce bug');
    } finally {
      setIsTriggeringRepro(false);
    }
  };

  const handleDiagnose = async (reproductionId: string) => {
    try {
      setIsTriggeringDiag(true);
      await triggerDiagnosis(id as string, reproductionId);
    } catch (err: any) {
      alert(err.message || 'Failed to start diagnosis');
    } finally {
      setIsTriggeringDiag(false);
    }
  };

  const handleGenerateFix = async (reproductionId: string, diagnosisId: string) => {
    try {
      setIsTriggeringRepair(true);
      await triggerRepair(id as string, reproductionId, diagnosisId);
    } catch (err: any) {
      alert(err.message || 'Failed to start repair');
    } finally {
      setIsTriggeringRepair(false);
    }
  };

  const handleVerifyRepair = async (repairId: string) => {
    try {
      await verifyRepair(repairId);
    } catch (err: any) {
      alert(err.message || 'Failed to start verification workflow');
    }
  };

  const handleConfirmPublish = async () => {
    if (!publishingRepair) return;
    try {
      await publishRepair(publishingRepair.id);
    } catch (err: any) {
      alert(err.message || 'Failed to start publication workflow');
    } finally {
      setPublishingRepair(null);
    }
  };

  const confidenceColor = (level: string | null) => {
    if (level === 'HIGH') return 'text-green-400 bg-green-500/10 border-green-500/20';
    if (level === 'MEDIUM') return 'text-yellow-400 bg-yellow-500/10 border-yellow-500/20';
    return 'text-red-400 bg-red-500/10 border-red-500/20';
  };

  const statusSteps = [
    { key: 'pending', label: 'Diagnosis queued' },
    { key: 'collecting_context', label: 'Collecting context' },
    { key: 'analyzing', label: 'Diagnosing root cause' },
    { key: 'validating', label: 'Validating diagnosis' },
    { key: 'completed', label: 'Complete' },
  ];

  const getStepState = (diagStatus: string, stepKey: string) => {
    const order = ['pending', 'collecting_context', 'analyzing', 'validating', 'completed'];
    const currentIdx = order.indexOf(diagStatus);
    const stepIdx = order.indexOf(stepKey);
    if (diagStatus === 'failed' || diagStatus === 'inconclusive') {
      if (stepIdx < currentIdx) return 'done';
      if (stepIdx === currentIdx) return 'error';
      return 'pending';
    }
    if (stepIdx < currentIdx) return 'done';
    if (stepIdx === currentIdx) return 'active';
    return 'pending';
  };

  // Find a reproduction with evidence to enable diagnosis
  const diagnosableRepro = reproductions.find(
    r => r.classification !== 'pending' && r.evidence && !r.evidence.error
  );

  if (error) {
    return (
      <main className="min-h-screen bg-neutral-950 text-neutral-200 font-mono p-8 flex items-center justify-center">
        <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-8 max-w-md w-full text-center">
          <div className="text-red-500 mb-4">
            <svg className="w-12 h-12 mx-auto" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
          </div>
          <h2 className="text-xl font-bold text-white mb-2">Error loading analysis</h2>
          <p className="text-red-400 mb-6">{error}</p>
          <button onClick={() => router.push('/')} className="text-blue-400 hover:text-blue-300 underline">Return to Dashboard</button>
        </div>
      </main>
    );
  }

  if (!analysis) {
    return (
      <main className="min-h-screen bg-neutral-950 text-neutral-200 font-mono p-8 flex items-center justify-center">
        <div className="text-center animate-pulse">
          <div className="w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
          <p>Loading analysis...</p>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-neutral-950 text-neutral-200 font-mono p-8 flex justify-center">
      <div className="w-full max-w-6xl">
        <header className="mb-8 flex justify-between items-center pb-4 border-b border-neutral-800">
          <div>
            <h1 className="text-2xl font-bold text-white flex items-center gap-3">
              {analysis.repository.name || 'Repository Analysis'}
              {analysis.status === 'completed' && <span className="text-xs bg-green-500/10 text-green-400 px-2 py-1 rounded border border-green-500/20">Completed</span>}
              {analysis.status === 'failed' && <span className="text-xs bg-red-500/10 text-red-400 px-2 py-1 rounded border border-red-500/20">Failed</span>}
              {(analysis.status === 'pending' || analysis.status === 'cloning' || analysis.status === 'analyzing') && 
                <span className="text-xs bg-blue-500/10 text-blue-400 px-2 py-1 rounded border border-blue-500/20 flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-blue-400 animate-pulse"></span>
                  {analysis.status.charAt(0).toUpperCase() + analysis.status.slice(1)}
                </span>
              }
            </h1>
            <a href={analysis.repository.url} target="_blank" rel="noopener noreferrer" className="text-sm text-neutral-500 hover:text-neutral-300 mt-1 inline-block">
              {analysis.repository.url}
            </a>
          </div>
          <button onClick={() => router.push('/')} className="text-sm bg-neutral-900 hover:bg-neutral-800 border border-neutral-800 text-neutral-300 px-4 py-2 rounded transition-colors">
            New Analysis
          </button>
        </header>

        {(analysis.status === 'pending' || analysis.status === 'cloning' || analysis.status === 'analyzing') && (
          <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-6 mb-8 shadow-lg">
            <h3 className="text-lg font-medium text-white mb-4 flex items-center gap-3">
              <div className="w-5 h-5 border-2 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
              Analyzing Repository...
            </h3>
            <ul className="space-y-3 text-sm text-neutral-400">
              <li className={`flex items-center gap-2 ${analysis.status !== 'pending' ? 'text-green-400' : ''}`}>
                <span>[✓] Validating repository url</span>
              </li>
              <li className={`flex items-center gap-2 ${analysis.status === 'analyzing' ? 'text-green-400' : analysis.status === 'cloning' ? 'text-white' : ''}`}>
                <span>{analysis.status === 'analyzing' ? '[✓]' : '[-]'} Cloning repository into secure workspace</span>
              </li>
              <li className={`flex items-center gap-2 ${analysis.status === 'analyzing' ? 'text-white' : ''}`}>
                <span>[-] Inspecting project structure and technologies</span>
              </li>
            </ul>
          </div>
        )}

        {analysis.status === 'failed' && (
          <div className="bg-red-950/20 border border-red-900/50 rounded-lg p-6 mb-8 text-red-400">
            <h3 className="text-lg font-medium mb-2">Analysis Failed</h3>
            <p className="font-sans text-sm">{analysis.error_message}</p>
          </div>
        )}

        {analysis.status === 'completed' && (
          <div className="space-y-6">
            {/* Top row: Repo Info + QA */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Repo Info */}
              <section className="bg-neutral-900 border border-neutral-800 rounded-lg p-6 shadow-sm">
                <h3 className="text-xs font-bold text-neutral-500 uppercase tracking-wider mb-4 border-b border-neutral-800 pb-2">Repository Intelligence</h3>
                <div className="space-y-4 text-sm">
                  <div className="flex justify-between"><span className="text-neutral-400">Primary Language</span><span className="text-white font-medium">{analysis.repository.primary_language || 'Unknown'}</span></div>
                  <div className="flex justify-between"><span className="text-neutral-400">Framework</span><span className="text-white font-medium">{analysis.repository.framework || 'None Detected'}</span></div>
                  <div className="flex justify-between"><span className="text-neutral-400">Total Files</span><span className="text-white font-medium">{analysis.repository.file_count.toLocaleString()}</span></div>
                  <div className="flex justify-between"><span className="text-neutral-400">Estimated LOC</span><span className="text-white font-medium">~{analysis.repository.estimated_loc.toLocaleString()}</span></div>
                </div>
              </section>

              {/* QA & Test Intelligence */}
              <section className="bg-neutral-900 border border-neutral-800 rounded-lg p-6 shadow-sm">
                <h3 className="text-xs font-bold text-neutral-500 uppercase tracking-wider mb-4 border-b border-neutral-800 pb-2 flex justify-between items-center">
                  QA & Test Intelligence
                  <button onClick={handleRunTests} disabled={isTriggeringTest || !analysis.testing.framework}
                    className="bg-blue-600 hover:bg-blue-500 disabled:bg-neutral-700 disabled:text-neutral-500 text-white text-xs px-3 py-1 rounded transition-colors">
                    {isTriggeringTest ? 'STARTING...' : '[ RUN EXISTING TESTS ]'}
                  </button>
                </h3>
                <div className="space-y-4 text-sm">
                  <div className="flex justify-between"><span className="text-neutral-400">Testing Framework</span><span className="text-white font-medium">{analysis.testing.framework || 'None Detected'}</span></div>
                  <div className="flex justify-between"><span className="text-neutral-400">Tests Found</span><span className="text-white font-medium">{analysis.testing.test_file_count}</span></div>
                </div>
                {testRuns.length > 0 && (
                  <div className="mt-4 border-t border-neutral-800 pt-4">
                    <h4 className="text-xs font-bold text-neutral-500 mb-2">TEST RUNS</h4>
                    <div className="space-y-2 max-h-64 overflow-y-auto pr-2">
                      {testRuns.map(run => (
                        <div key={run.id} className="text-xs bg-neutral-950 rounded border border-neutral-800 overflow-hidden">
                          <div 
                            className="flex justify-between items-center p-3 cursor-pointer hover:bg-neutral-900 transition-colors"
                            onClick={() => toggleTestRun(run.id)}
                          >
                            <div className="flex items-center gap-3">
                              <span className="text-neutral-400 font-mono">#{run.id.substring(0,4)}</span>
                              <span className="text-white font-medium">{run.framework || 'Unknown'}</span>
                            </div>
                            {run.status === 'running' ? (
                              <span className="text-blue-400 flex items-center gap-2">
                                <span className="w-2 h-2 rounded-full bg-blue-400 animate-pulse"></span>
                                Running...
                              </span>
                            ) : (
                              <div className="flex items-center gap-4">
                                <span className="text-neutral-400">
                                  {run.tests_passed} passed / {run.tests_total - run.tests_passed} failed
                                </span>
                                <span className={`font-bold px-2 py-0.5 rounded ${run.status === 'success' ? 'bg-green-500/10 text-green-500 border border-green-500/20' : 'bg-red-500/10 text-red-500 border border-red-500/20'}`}>
                                  {run.status === 'success' ? 'PASS' : 'FAIL'}
                                </span>
                              </div>
                            )}
                          </div>
                          
                          {expandedTestRuns.has(run.id) && run.status !== 'running' && (
                            <div className="p-3 border-t border-neutral-800 bg-neutral-900/50">
                              <div className="mb-3 grid grid-cols-2 gap-4">
                                <div>
                                  <span className="text-neutral-500 block mb-1">Command</span>
                                  <code className="text-neutral-300 bg-black px-2 py-1 rounded border border-neutral-800">{run.command || 'N/A'}</code>
                                </div>
                                <div>
                                  <span className="text-neutral-500 block mb-1">Exit Code</span>
                                  <span className={`font-mono ${run.exit_code === 0 ? 'text-green-400' : 'text-red-400'}`}>{run.exit_code !== null ? run.exit_code : 'N/A'}</span>
                                </div>
                              </div>
                              
                              {(run.stdout || run.stderr) && (
                                <div>
                                  <span className="text-neutral-500 block mb-1">Output</span>
                                  <pre className="text-[10px] text-neutral-400 bg-black p-3 rounded border border-neutral-800 overflow-x-auto max-h-40 whitespace-pre-wrap">
                                    {run.stdout}
                                    {run.stderr && `\n\n--- STDERR ---\n${run.stderr}`}
                                  </pre>
                                </div>
                              )}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </section>
            </div>

            {/* Bug Reproduction */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <section className="bg-neutral-900 border border-neutral-800 rounded-lg p-6 shadow-sm">
                <h3 className="text-xs font-bold text-neutral-500 uppercase tracking-wider mb-4 border-b border-neutral-800 pb-2">Bug Reproduction</h3>
                <textarea
                  className="w-full bg-neutral-950 border border-neutral-800 rounded p-3 text-sm text-neutral-300 focus:outline-none focus:border-blue-500 mb-4 h-28"
                  placeholder="Describe the bug..."
                  value={bugDescription}
                  onChange={(e) => setBugDescription(e.target.value)}
                />
                <button onClick={handleReproduceBug} disabled={isTriggeringRepro || !bugDescription}
                  className="w-full bg-blue-600 hover:bg-blue-500 disabled:bg-neutral-700 disabled:text-neutral-500 text-white font-medium px-4 py-2 rounded transition-colors">
                  {isTriggeringRepro ? 'STARTING...' : '[ REPRODUCE BUG ]'}
                </button>
              </section>

              {/* Reproduction Results */}
              <div className="space-y-4">
                {reproductions.map(repro => (
                  <div key={repro.id} className={`border rounded-lg shadow-sm overflow-hidden ${repro.classification === 'reproduced' ? 'border-red-900/50 bg-red-950/20' : repro.classification === 'not_reproduced' ? 'border-green-900/50 bg-green-950/20' : 'border-neutral-800 bg-neutral-900'}`}>
                    <div className="p-4">
                      <div className="flex justify-between items-center">
                        <h4 className={`font-bold uppercase tracking-wider text-sm ${repro.classification === 'reproduced' ? 'text-red-400' : repro.classification === 'not_reproduced' ? 'text-green-400' : 'text-neutral-400'}`}>
                          {repro.classification === 'reproduced' ? 'BUG REPRODUCED' : repro.classification === 'not_reproduced' ? 'BUG NOT REPRODUCED' : repro.classification === 'pending' ? 'QA ANALYSIS IN PROGRESS' : 'REPRODUCTION INCONCLUSIVE'}
                        </h4>
                        {repro.classification !== 'pending' && repro.evidence && !repro.evidence.error && (
                          <button
                            onClick={() => handleDiagnose(repro.id)}
                            disabled={isTriggeringDiag}
                            className="bg-purple-600 hover:bg-purple-500 disabled:bg-neutral-700 disabled:text-neutral-500 text-white text-xs px-3 py-1 rounded transition-colors"
                          >
                            {isTriggeringDiag ? 'STARTING...' : '[ DIAGNOSE BUG ]'}
                          </button>
                        )}
                      </div>
                      
                      {repro.classification === 'pending' && (
                        <div className="mt-3 space-y-1 text-sm text-neutral-400">
                          <p className="flex items-center gap-2"><span className="text-green-400">✓</span> Repository loaded</p>
                          <p className="flex items-center gap-2"><span className="w-2 h-2 bg-blue-500 rounded-full animate-pulse"></span> Generating reproduction test...</p>
                        </div>
                      )}

                      {repro.classification !== 'pending' && repro.evidence && (
                        <div className="mt-3 text-xs space-y-2 text-neutral-400">
                          {repro.classification === 'inconclusive' && repro.evidence.status === 'INCONCLUSIVE' ? (
                            <div className="bg-neutral-950 p-3 rounded border border-neutral-800 space-y-3">
                              <div>
                                <span className="text-neutral-500 block mb-1">Reason</span>
                                <span className="text-white">{repro.evidence.reason || 'Unknown error'}</span>
                              </div>
                              
                              {repro.evidence.command && repro.evidence.command !== 'N/A' && (
                                <div>
                                  <span className="text-neutral-500 block mb-1">Command</span>
                                  <code className="text-neutral-300 bg-black px-2 py-1 rounded border border-neutral-800">{repro.evidence.command}</code>
                                </div>
                              )}
                              
                              {repro.evidence.exit_code !== undefined && repro.evidence.exit_code !== null && (
                                <div>
                                  <span className="text-neutral-500 block mb-1">Exit Code</span>
                                  <span className="font-mono text-red-400">{repro.evidence.exit_code}</span>
                                </div>
                              )}
                              
                              {(repro.evidence.stdout || repro.evidence.stderr) && (
                                <div>
                                  <button 
                                    onClick={() => toggleReproOutput(repro.id)}
                                    className="text-blue-400 hover:text-blue-300 mb-2 uppercase font-bold tracking-wider"
                                  >
                                    {expandedReproOutputs.has(repro.id) ? '[ HIDE FULL OUTPUT ]' : '[ VIEW FULL OUTPUT ]'}
                                  </button>
                                  
                                  {expandedReproOutputs.has(repro.id) && (
                                    <pre className="text-[10px] text-neutral-400 bg-black p-3 rounded border border-neutral-800 overflow-x-auto max-h-40 whitespace-pre-wrap">
                                      {repro.evidence.stdout}
                                      {repro.evidence.stderr && `\n\n--- STDERR ---\n${repro.evidence.stderr}`}
                                    </pre>
                                  )}
                                </div>
                              )}
                            </div>
                          ) : (
                            <div>
                              {repro.confidence && <span>Confidence: {Math.round(repro.confidence * 100)}%</span>}
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* ═══════════════════════ DIAGNOSIS SECTION ═══════════════════════ */}
            {diagnoses.length > 0 && (
              <div className="space-y-6">
                <div className="border-t border-neutral-800 pt-6">
                  <h2 className="text-lg font-bold text-white mb-6 flex items-center gap-3">
                    <svg className="w-5 h-5 text-purple-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                    </svg>
                    Bug Diagnosis
                  </h2>
                </div>

                {diagnoses.map(diag => (
                  <div key={diag.id} className="border border-neutral-800 rounded-lg overflow-hidden bg-neutral-900 shadow-lg">
                    {/* Status / Timeline */}
                    {(diag.status !== 'completed' && diag.status !== 'failed' && diag.status !== 'inconclusive') && (
                      <div className="p-5 border-b border-neutral-800">
                        <h4 className="text-xs font-bold text-neutral-500 uppercase tracking-wider mb-4">Diagnosis Timeline</h4>
                        <div className="space-y-2">
                          {statusSteps.map(step => {
                            const state = getStepState(diag.status, step.key);
                            return (
                              <p key={step.key} className={`flex items-center gap-2 text-sm ${state === 'done' ? 'text-green-400' : state === 'active' ? 'text-white' : 'text-neutral-600'}`}>
                                {state === 'done' && <span>✓</span>}
                                {state === 'active' && <span className="w-2 h-2 bg-blue-500 rounded-full animate-pulse"></span>}
                                {state === 'pending' && <span className="text-neutral-700">○</span>}
                                {step.label}
                              </p>
                            );
                          })}
                        </div>
                      </div>
                    )}

                    {/* Failed */}
                    {diag.status === 'failed' && (
                      <div className="p-5 bg-red-950/20">
                        <h4 className="text-sm font-bold text-red-400 uppercase tracking-wider mb-2">Diagnosis Failed</h4>
                        <p className="text-sm text-red-300">{diag.error_message || 'An unknown error occurred.'}</p>
                      </div>
                    )}

                    {/* Completed / Inconclusive */}
                    {(diag.status === 'completed' || diag.status === 'inconclusive') && (
                      <>
                        {/* Header with confidence */}
                        <div className="p-5 border-b border-neutral-800 flex justify-between items-start">
                          <div className="flex-1">
                            <h4 className="text-xs font-bold text-purple-400 uppercase tracking-wider mb-2">
                              {diag.status === 'inconclusive' ? 'DIAGNOSIS INCONCLUSIVE' : 'BUG DIAGNOSIS'}
                            </h4>
                            <p className="text-white text-sm">{diag.summary}</p>
                          </div>
                          {diag.confidence !== null && diag.confidence !== undefined && (
                            <div className={`ml-4 px-3 py-2 rounded border text-center ${confidenceColor(diag.confidence_level)}`}>
                              <div className="text-2xl font-bold">{Math.round(diag.confidence * 100)}%</div>
                              <div className="text-xs font-bold uppercase tracking-wider">{diag.confidence_level}</div>
                            </div>
                          )}
                        </div>

                        {/* Root Cause */}
                        {diag.root_cause && (
                          <div className="p-5 border-b border-neutral-800">
                            <h4 className="text-xs font-bold text-neutral-500 uppercase tracking-wider mb-3">Root Cause</h4>
                            <p className="text-sm text-neutral-200 leading-relaxed">{diag.root_cause}</p>
                          </div>
                        )}

                        {/* Failure Mechanism */}
                        {diag.failure_mechanism && (
                          <div className="p-5 border-b border-neutral-800">
                            <h4 className="text-xs font-bold text-neutral-500 uppercase tracking-wider mb-3">Failure Mechanism</h4>
                            <p className="text-sm text-neutral-300 leading-relaxed">{diag.failure_mechanism}</p>
                          </div>
                        )}

                        {/* Affected Files & Functions */}
                        <div className="grid grid-cols-1 md:grid-cols-2 border-b border-neutral-800">
                          {diag.affected_files && diag.affected_files.length > 0 && (
                            <div className="p-5 border-r border-neutral-800">
                              <h4 className="text-xs font-bold text-neutral-500 uppercase tracking-wider mb-3">Affected Files</h4>
                              <ul className="space-y-1">
                                {diag.affected_files.map((f: string, i: number) => (
                                  <li key={i} className="text-sm text-blue-400 flex items-center gap-2">
                                    <svg className="w-3 h-3 text-neutral-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                                    </svg>
                                    {f}
                                  </li>
                                ))}
                              </ul>
                            </div>
                          )}
                          {diag.affected_functions && diag.affected_functions.length > 0 && (
                            <div className="p-5">
                              <h4 className="text-xs font-bold text-neutral-500 uppercase tracking-wider mb-3">Affected Functions</h4>
                              <ul className="space-y-1">
                                {diag.affected_functions.map((fn: string, i: number) => (
                                  <li key={i} className="text-sm text-yellow-400 font-mono">{fn}()</li>
                                ))}
                              </ul>
                            </div>
                          )}
                        </div>

                        {/* Evidence */}
                        {diag.evidence && diag.evidence.length > 0 && (
                          <div className="p-5 border-b border-neutral-800">
                            <h4 className="text-xs font-bold text-neutral-500 uppercase tracking-wider mb-3">Evidence</h4>
                            <div className="space-y-3">
                              {diag.evidence.map((ev: any, i: number) => (
                                <div key={i} className="bg-neutral-950 border border-neutral-800 rounded p-3">
                                  <div className="flex items-center gap-2 mb-1">
                                    <span className={`text-xs font-bold uppercase px-2 py-0.5 rounded ${
                                      ev.type === 'stack_trace' ? 'bg-red-500/10 text-red-400' :
                                      ev.type === 'test_failure' ? 'bg-yellow-500/10 text-yellow-400' :
                                      ev.type === 'exception' ? 'bg-orange-500/10 text-orange-400' :
                                      'bg-blue-500/10 text-blue-400'
                                    }`}>{ev.type.replace('_', ' ')}</span>
                                    {ev.file && <span className="text-xs text-neutral-500">{ev.file}{ev.line ? `:${ev.line}` : ''}</span>}
                                  </div>
                                  <p className="text-xs text-neutral-300">{ev.description}</p>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Code Context */}
                        {diag.code_context && diag.code_context.length > 0 && (
                          <div className="p-5 border-b border-neutral-800">
                            <h4 className="text-xs font-bold text-neutral-500 uppercase tracking-wider mb-3">Relevant Code</h4>
                            <div className="space-y-2">
                              {diag.code_context.map((cc: any, i: number) => (
                                <div key={i} className="bg-neutral-950 border border-neutral-800 rounded overflow-hidden">
                                  <button
                                    onClick={() => setExpandedCode(expandedCode === `${diag.id}-${i}` ? null : `${diag.id}-${i}`)}
                                    className="w-full flex justify-between items-center p-3 text-xs hover:bg-neutral-800/50 transition-colors"
                                  >
                                    <span className="text-blue-400">{cc.file} <span className="text-neutral-500">lines {cc.start_line}–{cc.end_line}</span></span>
                                    <span className="text-neutral-600">{expandedCode === `${diag.id}-${i}` ? '▾' : '▸'}</span>
                                  </button>
                                  {expandedCode === `${diag.id}-${i}` && (
                                    <pre className="p-3 text-[10px] text-neutral-300 overflow-x-auto border-t border-neutral-800 bg-black/40 max-h-64 overflow-y-auto">
                                      {cc.content}
                                    </pre>
                                  )}
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Alternative Causes */}
                        {diag.alternative_causes && diag.alternative_causes.length > 0 && (
                          <div className="p-5">
                            <h4 className="text-xs font-bold text-neutral-500 uppercase tracking-wider mb-3">Alternative Causes</h4>
                            <div className="space-y-2">
                              {diag.alternative_causes.map((ac: any, i: number) => (
                                <div key={i} className="flex justify-between items-center text-sm bg-neutral-950 border border-neutral-800 rounded p-3">
                                  <span className="text-neutral-300">{ac.description}</span>
                                  <span className="text-neutral-500 text-xs ml-4">{Math.round(ac.confidence * 100)}%</span>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* GENERATE FIX BUTTON */}
                        {diag.status === 'completed' && (
                          <div className="p-5 border-t border-neutral-800 bg-neutral-950 flex justify-end">
                            <button
                              onClick={() => handleGenerateFix(diag.reproduction_id, diag.id)}
                              disabled={isTriggeringRepair}
                              className="bg-blue-600 hover:bg-blue-500 disabled:bg-neutral-700 disabled:text-neutral-500 text-white font-bold py-2 px-6 rounded transition-colors"
                            >
                              {isTriggeringRepair ? 'STARTING...' : '[ GENERATE FIX ]'}
                            </button>
                          </div>
                        )}
                      </>
                    )}
                  </div>
                ))}
              </div>
            )}

            {/* ═══════════════════════ REPAIR SECTION ═══════════════════════ */}
            {repairs.length > 0 && (
              <div className="space-y-6">
                <div className="border-t border-neutral-800 pt-6">
                  <h2 className="text-lg font-bold text-white mb-6 flex items-center gap-3">
                    <svg className="w-5 h-5 text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
                    </svg>
                    Repair Candidate
                  </h2>
                </div>

                {repairs.map(repair => (
                  <div key={repair.id} className="border border-neutral-800 rounded-lg overflow-hidden bg-neutral-900 shadow-lg">
                    {/* Status Bar */}
                    <div className="p-5 border-b border-neutral-800 flex justify-between items-start">
                      <div className="flex-1">
                        <h4 className="text-xs font-bold text-blue-400 uppercase tracking-wider mb-2">
                          STATUS: {repair.status.replace('_', ' ').toUpperCase()}
                        </h4>
                        {repair.summary ? (
                          <p className="text-white text-sm">{repair.summary}</p>
                        ) : (
                          <p className="text-neutral-500 text-sm italic">Generating repair strategy...</p>
                        )}
                      </div>
                      {repair.confidence && (
                        <div className="ml-4 px-3 py-2 rounded border border-blue-500/20 bg-blue-500/10 text-center text-blue-400">
                          <div className="text-2xl font-bold">{Math.round(repair.confidence * 100)}%</div>
                          <div className="text-xs font-bold uppercase tracking-wider">CONFIDENCE</div>
                        </div>
                      )}
                    </div>

                    {/* Progress States */}
                    {(['pending', 'generating', 'validating', 'applied', 'tested'].includes(repair.status)) && (
                      <div className="p-5 border-b border-neutral-800">
                        <div className="flex items-center gap-3 text-sm text-neutral-400">
                          <span className="w-3 h-3 border-2 border-blue-500 border-t-transparent rounded-full animate-spin"></span>
                          <span>
                            {repair.status === 'pending' && 'Queued...'}
                            {repair.status === 'generating' && 'Analyzing code and generating candidate patch...'}
                            {repair.status === 'validating' && 'Validating patch safety and constraints...'}
                            {repair.status === 'applied' && 'Creating temporary workspace and applying patch...'}
                            {repair.status === 'tested' && 'Running reproduction test suite in isolated workspace...'}
                          </span>
                        </div>
                      </div>
                    )}

                    {/* Error / Rejected State */}
                    {(repair.status === 'error' || repair.status === 'rejected') && (
                      <div className="p-5 bg-red-950/20 border-b border-neutral-800">
                        <h4 className="text-sm font-bold text-red-400 uppercase tracking-wider mb-2">Repair Failed</h4>
                        <p className="text-sm text-red-300">{repair.error_message}</p>
                      </div>
                    )}

                    {/* Files Changed */}
                    {(repair.status === 'completed' || repair.status === 'failed') && repair.files_changed !== null && (
                      <div className="p-5 border-b border-neutral-800">
                        <h4 className="text-xs font-bold text-neutral-500 uppercase tracking-wider mb-3">Files Changed</h4>
                        <div className="flex items-center gap-4 text-sm font-mono bg-neutral-950 p-3 rounded border border-neutral-800">
                          <span className="text-white">{repair.files_changed} file(s)</span>
                          <span className="text-green-400">+{repair.lines_added}</span>
                          <span className="text-red-400">-{repair.lines_removed}</span>
                        </div>
                      </div>
                    )}

                    {/* Test Results */}
                    {(repair.status === 'completed' || repair.status === 'failed') && repair.test_result && (
                      <div className="p-5 border-b border-neutral-800">
                        <h4 className="text-xs font-bold text-neutral-500 uppercase tracking-wider mb-3">Reproduction Test Result</h4>
                        <div className={`p-4 rounded border ${repair.test_result.status === 'passed' ? 'bg-green-950/20 border-green-900/50' : 'bg-red-950/20 border-red-900/50'}`}>
                          <div className="flex justify-between items-center mb-2">
                            <span className={`font-bold uppercase ${repair.test_result.status === 'passed' ? 'text-green-400' : 'text-red-400'}`}>
                              {repair.test_result.status === 'passed' ? 'PASS ✓' : 'FAIL ✗'}
                            </span>
                            <span className="text-xs text-neutral-500">Workspace: {repair.workspace_id || 'isolated'}</span>
                          </div>
                          {repair.test_result.status === 'passed' && (
                            <p className="text-sm text-green-300 mt-2">The candidate patch successfully resolved the reproduction test in the temporary workspace.</p>
                          )}
                          {repair.test_result.status === 'failed' && (
                            <div className="mt-2 text-xs text-red-300 font-mono bg-black/40 p-2 rounded max-h-32 overflow-y-auto">
                              {repair.test_result.stderr || repair.test_result.stdout}
                            </div>
                          )}
                        </div>
                      </div>
                    )}

                    {/* Diff View */}
                    {(repair.status === 'completed' || repair.status === 'failed') && repair.patch && (
                      <div className="p-5">
                        <div className="flex justify-between items-center mb-3">
                          <h4 className="text-xs font-bold text-neutral-500 uppercase tracking-wider">Generated Patch</h4>
                          <span className="text-[10px] uppercase bg-yellow-500/10 text-yellow-400 px-2 py-0.5 rounded border border-yellow-500/20">Original Repository Unchanged</span>
                        </div>
                        <pre className="p-4 text-xs font-mono bg-black rounded border border-neutral-800 overflow-x-auto whitespace-pre">
                          {repair.patch.split('\n').map((line: string, i: number) => {
                            let color = 'text-neutral-300';
                            if (line.startsWith('+') && !line.startsWith('+++')) color = 'text-green-400 bg-green-500/10 block w-full';
                            if (line.startsWith('-') && !line.startsWith('---')) color = 'text-red-400 bg-red-500/10 block w-full';
                            if (line.startsWith('@@')) color = 'text-blue-400';
                            return <span key={i} className={color}>{line}{'\n'}</span>;
                          })}
                        </pre>
                        
                        {repair.status === 'completed' && (
                          <div className="mt-4 pt-4 border-t border-neutral-800 text-center">
                            {repair.final_status === 'VERIFIED_FIXED' ? (
                              <div className="flex flex-col items-center">
                                <div className="bg-green-950/20 text-green-400 p-3 rounded border border-green-900/50 mb-3 font-bold w-full">
                                  ✓ REPAIR VERIFIED SUCCESSFULLY
                                </div>
                                {publicationsMap[repair.id] ? (
                                  <div className="w-full text-left mt-2 p-4 border border-neutral-700 rounded bg-neutral-900/80">
                                    <h5 className="font-bold text-sm mb-2 uppercase text-neutral-300">GitHub Publication</h5>
                                    <div className="flex flex-col space-y-2 text-xs">
                                      <div className="flex justify-between">
                                        <span className="text-neutral-500">Status:</span>
                                        <span className={`font-bold uppercase ${
                                          publicationsMap[repair.id]?.status === 'PUBLISHED' ? 'text-green-400' :
                                          publicationsMap[repair.id]?.status?.includes('FAIL') ? 'text-red-400' :
                                          'text-blue-400'
                                        }`}>{publicationsMap[repair.id]?.status}</span>
                                      </div>
                                      
                                      {publicationsMap[repair.id]?.status === 'PUBLISHED' && publicationsMap[repair.id]?.pull_request_url && (
                                        <div className="mt-2 text-center pt-2 border-t border-neutral-800">
                                          <a href={publicationsMap[repair.id]!.pull_request_url!} target="_blank" rel="noreferrer" className="inline-block bg-neutral-800 hover:bg-neutral-700 text-white font-bold py-2 px-6 rounded transition-colors border border-neutral-600">
                                            VIEW PULL REQUEST #{publicationsMap[repair.id]!.pull_request_number}
                                          </a>
                                        </div>
                                      )}
                                      
                                      {publicationsMap[repair.id]?.error_message && (
                                        <div className="bg-red-950/30 text-red-400 p-2 rounded mt-2 border border-red-900/50">
                                          {publicationsMap[repair.id]?.error_message}
                                        </div>
                                      )}
                                    </div>
                                  </div>
                                ) : publishingRepair?.id === repair.id ? (
                                  <div className="w-full mt-2 p-4 border border-purple-500/30 rounded bg-purple-950/10 text-left">
                                    <h5 className="font-bold text-sm mb-2 text-purple-400">CREATE GITHUB PULL REQUEST</h5>
                                    <p className="text-xs text-neutral-400 mb-4">This will publish the verified repair to GitHub. Fixyron branch will be created and pushed. No automatic merge will occur.</p>
                                    <div className="flex justify-end space-x-3">
                                      <button onClick={() => setPublishingRepair(null)} className="text-xs font-bold text-neutral-500 hover:text-white px-3 py-1">CANCEL</button>
                                      <button onClick={handleConfirmPublish} className="bg-purple-600 hover:bg-purple-500 text-white text-xs font-bold py-2 px-4 rounded">CONFIRM PUBLISH</button>
                                    </div>
                                  </div>
                                ) : (
                                  <button onClick={() => setPublishingRepair(repair)} className="bg-purple-600 hover:bg-purple-500 text-white font-bold py-2 px-6 rounded transition-colors w-full sm:w-auto">
                                    [ CREATE PULL REQUEST ]
                                  </button>
                                )}
                              </div>
                            ) : repair.final_status === 'REPAIR_FAILED' || repair.final_status === 'REPAIR_STALLED' ? (
                              <div className="bg-red-950/20 text-red-400 p-3 rounded border border-red-900/50 mb-3 font-bold">
                                ✗ {repair.final_status.replace('_', ' ')}
                              </div>
                            ) : repair.final_status === 'INCONCLUSIVE' ? (
                              <div className="bg-yellow-950/20 text-yellow-400 p-3 rounded border border-yellow-900/50 mb-3 font-bold">
                                ? VERIFICATION INCONCLUSIVE
                              </div>
                            ) : (
                              <>
                                <p className="text-xs text-neutral-500 mb-3">This patch has passed the reproduction test. It has NOT yet passed full verification.</p>
                                <button 
                                  onClick={() => handleVerifyRepair(repair.id)}
                                  className="bg-purple-600 hover:bg-purple-500 text-white font-bold py-2 px-6 rounded transition-colors"
                                >
                                  [ VERIFY REPAIR (AUTONOMOUS LOOP) ]
                                </button>
                              </>
                            )}
                          </div>
                        )}
                      </div>
                    )}

                    {/* Attempts Timeline */}
                    {repairAttemptsMap[repair.id] && repairAttemptsMap[repair.id].length > 0 && (
                      <div className="p-5 border-t border-neutral-800 bg-neutral-950/50">
                        <h4 className="text-xs font-bold text-neutral-500 uppercase tracking-wider mb-4">Autonomous Repair Attempts</h4>
                        <div className="space-y-4">
                          {repairAttemptsMap[repair.id].map(attempt => (
                            <div key={attempt.id} className="border border-neutral-800 rounded bg-neutral-900 overflow-hidden">
                              <div className="p-3 border-b border-neutral-800 flex justify-between items-center bg-neutral-950">
                                <span className="font-bold text-sm text-white">Attempt #{attempt.attempt_number}</span>
                                <span className={`text-xs px-2 py-1 rounded font-bold uppercase ${
                                  attempt.status === 'passed' ? 'bg-green-500/10 text-green-400 border border-green-500/20' : 
                                  attempt.status === 'failed' ? 'bg-red-500/10 text-red-400 border border-red-500/20' : 
                                  'bg-blue-500/10 text-blue-400 border border-blue-500/20'
                                }`}>{attempt.status}</span>
                              </div>
                              <div className="p-4 text-xs space-y-3">
                                {attempt.strategy && attempt.strategy.strategy && (
                                  <div>
                                    <span className="text-neutral-500 block mb-1 font-bold">Strategy:</span>
                                    <p className="text-neutral-300">{attempt.strategy.strategy}</p>
                                  </div>
                                )}
                                {attempt.review && (
                                  <div className="bg-black/30 p-3 rounded border border-neutral-800">
                                    <span className="text-neutral-500 block mb-1 font-bold">Reviewer Verdict: <span className={attempt.review.verdict === 'PASS' ? 'text-green-400' : attempt.review.verdict === 'FAIL' ? 'text-red-400' : 'text-yellow-400'}>{attempt.review.verdict}</span></span>
                                    <p className="text-neutral-300">{attempt.review.summary}</p>
                                    {attempt.review.reason && <p className="text-neutral-400 mt-1 italic">{attempt.review.reason}</p>}
                                  </div>
                                )}
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}

          </div>
        )}
      </div>
    </main>
  );
}
