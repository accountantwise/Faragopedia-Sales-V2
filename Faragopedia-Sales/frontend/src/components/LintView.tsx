import React, { useState } from 'react';
import { Activity, Loader2, AlertCircle, AlertTriangle, Lightbulb } from 'lucide-react';

import { API_BASE } from '../config';

interface LintFinding {
  severity: 'error' | 'warning' | 'suggestion';
  page: string;
  description: string;
}

interface LintReport {
  findings: LintFinding[];
  summary: string;
}

const SEVERITY_CONFIG = {
  error: {
    label: 'Errors',
    icon: <AlertCircle className="w-4 h-4 text-red-500" />,
    cardClass: 'bg-red-50 border-red-200',
    badgeClass: 'bg-red-100 text-red-700',
  },
  warning: {
    label: 'Warnings',
    icon: <AlertTriangle className="w-4 h-4 text-amber-500" />,
    cardClass: 'bg-amber-50 border-amber-200',
    badgeClass: 'bg-amber-100 text-amber-700',
  },
  suggestion: {
    label: 'Suggestions',
    icon: <Lightbulb className="w-4 h-4 text-blue-500" />,
    cardClass: 'bg-blue-50 border-blue-200',
    badgeClass: 'bg-blue-100 text-blue-700',
  },
};

const LintView: React.FC = () => {
  const [report, setReport] = useState<LintReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const runLint = async () => {
    setLoading(true);
    setError(null);
    setReport(null);
    try {
      const response = await fetch(`${API_BASE}/lint`, { method: 'POST' });
      if (!response.ok) throw new Error('Lint request failed');
      const data: LintReport = await response.json();
      setReport(data);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-12 max-w-4xl mx-auto">
      <h1 className="text-4xl font-extrabold text-gray-900 mb-6 tracking-tight">Wiki Lint</h1>
      <p className="text-xl text-gray-500 mb-8 leading-relaxed">
        Deep AI analysis — orphan pages, contradictions, missing entities, and data gaps.
      </p>

      <button
        onClick={runLint}
        disabled={loading}
        className="flex items-center px-6 py-3 bg-blue-600 text-white rounded-xl font-semibold hover:bg-blue-700 transition-colors disabled:opacity-50 mb-8 shadow-sm"
      >
        {loading
          ? <Loader2 className="w-5 h-5 animate-spin mr-2" />
          : <Activity className="w-5 h-5 mr-2" />
        }
        Lint
      </button>

      {loading && (
        <div className="flex items-center space-x-3 text-gray-500">
          <Loader2 className="w-5 h-5 animate-spin" />
          <span>Analysing wiki — this may take a moment...</span>
        </div>
      )}

      {error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-xl text-red-700 text-sm">
          {error}
        </div>
      )}

      {report && (
        <div className="space-y-6">
          <p className="text-gray-600 font-medium">{report.summary}</p>

          {(['error', 'warning', 'suggestion'] as const).map(severity => {
            const findings = report.findings.filter(f => f.severity === severity);
            if (findings.length === 0) return null;
            const config = SEVERITY_CONFIG[severity];
            return (
              <div key={severity}>
                <h3 className="flex items-center space-x-2 text-sm font-semibold text-gray-700 uppercase tracking-wider mb-3">
                  {config.icon}
                  <span>{config.label} ({findings.length})</span>
                </h3>
                <ul className="space-y-2">
                  {findings.map((finding, i) => (
                    <li key={i} className={`p-4 rounded-xl border ${config.cardClass}`}>
                      <span className={`inline-block text-xs font-mono px-2 py-0.5 rounded-md mb-1 ${config.badgeClass}`}>
                        {finding.page}
                      </span>
                      <p className="text-sm text-gray-700">{finding.description}</p>
                    </li>
                  ))}
                </ul>
              </div>
            );
          })}

          {report.findings.length === 0 && (
            <p className="text-green-600 font-medium">Wiki is clean — no issues found.</p>
          )}
        </div>
      )}
    </div>
  );
};

export default LintView;
