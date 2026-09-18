'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { analyzeRepository } from '../lib/api';

export default function Home() {
  const [url, setUrl] = useState('');
  const [bugDescription, setBugDescription] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const router = useRouter();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const response = await analyzeRepository(url, bugDescription);
      router.push(`/analysis/${response.analysis_id}`);
    } catch (err: any) {
      setError(err.message || 'An unexpected error occurred.');
      setLoading(false);
    }
  };

  return (
    <main className="min-h-screen bg-neutral-950 text-neutral-200 font-mono p-8 flex flex-col items-center justify-center">
      <div className="w-full max-w-2xl">
        <header className="mb-12 text-center">
          <h1 className="text-4xl font-bold tracking-tight text-white mb-2">FIXYRON</h1>
          <p className="text-neutral-500">Autonomous Software QA & Bug-Fixing Agent</p>
        </header>

        <div className="bg-neutral-900 border border-neutral-800 rounded-lg shadow-xl p-8">
          <h2 className="text-xl font-semibold text-white mb-6">Analyze Repository</h2>
          
          <form onSubmit={handleSubmit} className="space-y-6">
            <div>
              <label htmlFor="url" className="block text-sm font-medium text-neutral-400 mb-2">
                GitHub Repository URL
              </label>
              <input
                id="url"
                type="url"
                placeholder="https://github.com/owner/repository"
                required
                className="w-full bg-neutral-950 border border-neutral-800 rounded px-4 py-3 text-white focus:outline-none focus:ring-2 focus:ring-blue-500/50 transition-colors"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
              />
            </div>

            <div>
              <label htmlFor="bug" className="block text-sm font-medium text-neutral-400 mb-2">
                Bug Description <span className="text-neutral-600">(Optional)</span>
              </label>
              <textarea
                id="bug"
                rows={4}
                placeholder="Describe the problem..."
                className="w-full bg-neutral-950 border border-neutral-800 rounded px-4 py-3 text-white focus:outline-none focus:ring-2 focus:ring-blue-500/50 transition-colors"
                value={bugDescription}
                onChange={(e) => setBugDescription(e.target.value)}
              />
            </div>

            {error && (
              <div className="bg-red-950/50 border border-red-900/50 text-red-400 px-4 py-3 rounded text-sm">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-blue-600 hover:bg-blue-700 text-white font-medium py-3 px-4 rounded transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? 'Starting Analysis...' : 'Analyze Repository'}
            </button>
          </form>
        </div>
      </div>
    </main>
  );
}
